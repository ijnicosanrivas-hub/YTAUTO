"""Orquestador: ejecuta el flujo fase a fase con estado persistente.

`step()` ejecuta como mucho UNA fase y devuelve; así la cola (fase 3) controla cuándo y
cuántas tareas de Claude se lanzan. `run()` encadena pasos hasta que el proyecto se
bloquea, termina o falla.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ..agents.base import Agent, AgentContext, ModelConfig
from ..agents.registry import build_agents
from ..core.errors import AcceptanceError, PhaseBlocked, ProviderError
from ..core.events import EventBus
from ..core.models import CorrectionRequest, PhaseStatus, ProjectSpec, ProjectStatus, new_id, utcnow
from ..core.narrative import NarrativeTemplate
from ..core.workspace import ProjectMemory, Workspace
from ..llm.base import AuthenticationError, LLMError, LLMProvider, UsageLimitError
from ..providers.interfaces import ProviderGateway
from .pipeline import PHASES, PIPELINE, PhaseDef, downstream
from .state import Approval, PhaseRecord, ProjectRecord, StateStore

log = logging.getLogger("ytauto.orchestrator")

SCENE_SCOPED = {"scene_prep", "resource_generation"}

StepOutcome = Literal["ran", "waiting_approval", "blocked", "paused", "cancelled", "completed", "error", "idle",
                      "usage_limit", "auth_error"]


@dataclass
class StepResult:
    outcome: StepOutcome
    phase: str | None = None
    message: str = ""
    resets_at: str | None = None


@dataclass
class OrchestratorSettings:
    projects_dir: Path
    review_threshold: int = 75
    max_correction_rounds: int = 2
    voice_llm_pronunciation: bool = False
    publish_privacy: str = "private"
    publish_auth_ttl_hours: int = 24
    extra: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    def __init__(self, store: StateStore, llm: LLMProvider, providers: ProviderGateway,
                 settings: OrchestratorSettings, events: EventBus | None = None,
                 models: ModelConfig | None = None, narrative: NarrativeTemplate | None = None,
                 agents: dict[str, Agent] | None = None,
                 cost_reader: Callable[[str], list[dict]] | None = None):
        self.store = store
        self.llm = llm
        self.providers = providers
        self.settings = settings
        self.events = events or EventBus()
        self.models = models or ModelConfig.load()
        self.narrative = narrative or NarrativeTemplate.load()
        self.agents = agents or build_agents()
        self.cost_reader = cost_reader or (lambda pid: [])

    # ================================================================== proyectos
    def create_project(self, spec: ProjectSpec, project_id: str | None = None) -> str:
        pid = project_id or new_id("prj_")
        self.store.create_project(ProjectRecord(id=pid, spec=spec))
        Workspace(self.settings.projects_dir, pid)
        self.events.emit("project.created", project_id=pid, data={"name": spec.name})
        return pid

    def _set_project_status(self, pid: str, status: ProjectStatus, reason: str | None = None) -> None:
        rec = self.store.get_project(pid)
        rec.status, rec.blocked_reason = status, reason
        self.store.save_project(rec)
        self.events.emit("project.status", project_id=pid, data={"status": status.value, "reason": reason})

    def pause(self, pid: str) -> None:
        self._set_project_status(pid, ProjectStatus.PAUSED)

    def recover_interrupted(self, pid: str) -> int:
        """Fases que quedaron 'running'/'assigned' por una caída vuelven a 'pending'."""
        n = 0
        for ph in self.store.list_phases(pid):
            if ph.status in (PhaseStatus.RUNNING, PhaseStatus.ASSIGNED):
                self._set_phase(ph, PhaseStatus.PENDING, error="Reanudada tras interrupción")
                n += 1
        return n

    def resume(self, pid: str) -> None:
        """Reanuda un proyecto pausado/bloqueado sin repetir fases completadas."""
        self.recover_interrupted(pid)
        for ph in self.store.list_phases(pid):
            if ph.status is PhaseStatus.BLOCKED and ph.blocked_code in ("usage_limit", "auth", "budget_exceeded",
                                                                           "spend_not_authorized", "provider"):
                self._set_phase(ph, PhaseStatus.PENDING)
        self._set_project_status(pid, ProjectStatus.ACTIVE)

    def cancel(self, pid: str) -> None:
        self._set_project_status(pid, ProjectStatus.CANCELLED)

    def retry_phase(self, pid: str, phase: str) -> None:
        ph = self.store.get_phase(pid, phase)
        if ph.status in (PhaseStatus.ERROR, PhaseStatus.BLOCKED):
            self._set_phase(ph, PhaseStatus.PENDING)
        rec = self.store.get_project(pid)
        if rec.status in (ProjectStatus.ERROR, ProjectStatus.BLOCKED):
            self._set_project_status(pid, ProjectStatus.ACTIVE)

    def redo_scenes(self, pid: str, scenes: list[int], from_phase: str = "resource_generation", reason: str = "") -> None:
        """Rehace solo unas escenas desde una fase; el resto se reutiliza (render incremental)."""
        self._invalidate(pid, [{"phase": from_phase, "scenes": scenes, "reasons": [reason or "Petición del usuario"]}])
        self._set_project_status(pid, ProjectStatus.ACTIVE)

    # ================================================================== aprobaciones
    def approve(self, pid: str, gate: str, approved: bool = True, note: str = "") -> Approval:
        if gate not in ("script_approval", "final_approval", "publish_decision") \
                and not gate.startswith(("publish:", "spend:")):
            raise ValueError(f"Puerta de aprobación desconocida: {gate}")
        if gate in PHASES:
            current = self.store.get_phase(pid, gate)
            if current.status is not PhaseStatus.IN_REVIEW:
                raise ValueError(f"'{gate}' no está esperando aprobación (estado: {current.status.value})")
        if gate.startswith("publish:") or gate == "publish_decision":
            prep = self.store.get_phase(pid, "publish_prep")
            if not prep.status.is_done:
                raise ValueError("La publicación solo puede autorizarse cuando el material está preparado")
        expires = None
        if gate.startswith("publish:"):
            from datetime import timedelta
            expires = (utcnow() + timedelta(hours=self.settings.publish_auth_ttl_hours)).isoformat()
        a = self.store.add_approval(Approval(project_id=pid, gate=gate, approved=approved, note=note, expires_at=expires))
        self.events.emit("approval", project_id=pid, data=a.model_dump())
        if gate in PHASES:
            ph = self.store.get_phase(pid, gate)
            if approved:
                self._set_phase(ph, PhaseStatus.APPROVED, summary=note or "Aprobado por el usuario")
            elif gate == "script_approval":
                # Rechazo del guion: el guionista lo reescribe con el comentario del usuario.
                self._invalidate(pid, [{"phase": "script", "scenes": None,
                                        "reasons": [note or "Guion rechazado por el usuario"]}], include_approvals=True)
            else:
                # Rechazo final: queda a la espera de instrucciones (redo_scenes / retry_phase).
                self._set_phase(ph, PhaseStatus.IN_REVIEW, summary=f"Rechazado: {note}" if note else "Rechazado")
        elif gate.startswith("spend:"):
            # Autorización de gasto en un proveedor de pago: se desbloquean las fases que la esperaban.
            if approved:
                for ph in self.store.list_phases(pid):
                    if ph.status is PhaseStatus.BLOCKED and ph.blocked_code in ("spend_not_authorized",
                                                                                "budget_exceeded"):
                        self._set_phase(ph, PhaseStatus.PENDING)
                rec = self.store.get_project(pid)
                if rec.status is ProjectStatus.BLOCKED:
                    self._set_project_status(pid, ProjectStatus.ACTIVE)
        elif gate.startswith("publish:") or gate == "publish_decision":
            ph = self.store.get_phase(pid, "publish")
            if ph.status is PhaseStatus.BLOCKED:
                self._set_phase(ph, PhaseStatus.PENDING)
        return a

    def _valid_publish_auths(self, pid: str) -> dict[str, str]:
        now = utcnow().isoformat()
        out = {}
        for a in self.store.get_approvals(pid):
            if a.gate.startswith("publish:") and a.approved and (a.expires_at is None or a.expires_at > now):
                out[a.gate.split(":", 1)[1]] = a.id
        return out

    def is_spend_authorized(self, pid: str | None, provider_id: str) -> bool:
        if pid is None:
            return False
        return self._gate_approved(pid, f"spend:{provider_id}")

    def _gate_approved(self, pid: str, gate: str) -> bool:
        apps = [a for a in self.store.get_approvals(pid) if a.gate == gate]
        return bool(apps) and apps[-1].approved

    # ================================================================== ejecución
    def next_phase(self, pid: str) -> PhaseDef | None:
        records = {r.phase: r for r in self.store.list_phases(pid)}
        for p in PIPELINE:
            r = records[p.id]
            if r.status.is_done:
                continue
            if all(records[d].status.is_done for d in p.depends_on):
                return p
        return None

    def step(self, pid: str) -> StepResult:
        project = self.store.get_project(pid)
        if project.status is ProjectStatus.CANCELLED:
            return StepResult("cancelled")
        if project.status is ProjectStatus.PAUSED:
            return StepResult("paused")
        if project.status is ProjectStatus.COMPLETED:
            return StepResult("completed")
        phase = self.next_phase(pid)
        if phase is None:
            if all(r.status.is_done for r in self.store.list_phases(pid)):
                self._set_project_status(pid, ProjectStatus.COMPLETED)
                return StepResult("completed")
            return StepResult("idle")
        record = self.store.get_phase(pid, phase.id)
        if record.status in (PhaseStatus.ERROR,):
            return StepResult("error", phase.id, record.error or "")
        if record.status is PhaseStatus.BLOCKED:
            return StepResult("blocked", phase.id, record.error or "")
        if record.status is PhaseStatus.IN_REVIEW and phase.kind == "approval" and phase.agent is None:
            return StepResult("waiting_approval", phase.id)

        # ---- puertas de aprobación
        if phase.kind == "approval" and phase.agent is None:
            if phase.id == "script_approval" and not project.spec.require_script_approval:
                self._set_phase(record, PhaseStatus.APPROVED, summary="Aprobación automática (modo automático)")
                return StepResult("ran", phase.id)
            if self._gate_approved(pid, phase.id):
                self._set_phase(record, PhaseStatus.APPROVED)
                return StepResult("ran", phase.id)
            self._set_phase(record, PhaseStatus.IN_REVIEW, summary="Esperando aprobación del usuario")
            return StepResult("waiting_approval", phase.id)

        if phase.id == "publish":
            auths = self._valid_publish_auths(pid)
            if not auths and not self._gate_approved(pid, "publish_decision"):
                self._set_phase(record, PhaseStatus.BLOCKED, error="Esperando autorización expresa de publicación",
                                blocked_code="publish_authorization")
                return StepResult("waiting_approval", phase.id)

        return self._run_agent_phase(project, phase, record)

    def run(self, pid: str, max_steps: int = 200) -> StepResult:
        last = StepResult("idle")
        for _ in range(max_steps):
            last = self.step(pid)
            if last.outcome != "ran":
                return last
        return last

    # ------------------------------------------------------------------
    def _context(self, project: ProjectRecord, record: PhaseRecord) -> AgentContext:
        ws = Workspace(self.settings.projects_dir, project.id)
        settings = {
            "review_threshold": self.settings.review_threshold,
            "max_correction_rounds": self.settings.max_correction_rounds,
            "correction_rounds": project.correction_rounds,
            "voice_llm_pronunciation": self.settings.voice_llm_pronunciation,
            "publish_privacy": self.settings.publish_privacy,
            "publish_authorizations": self._valid_publish_auths(project.id),
            "llm_usage": self.store.llm_usage(project.id),
            "costs": self.cost_reader(project.id),
            **self.settings.extra,
        }

        def on_usage(agent: str, phase: str, usage) -> None:
            self.store.record_llm_usage(project.id, agent, phase, usage.model_dump())

        return AgentContext(
            project_id=project.id, spec=project.spec, workspace=ws, memory=ProjectMemory(ws), llm=self.llm,
            providers=self.providers, models=self.models, narrative=self.narrative, events=self.events,
            scene_filter=set(record.scene_filter) if record.scene_filter is not None else None,
            corrections=record.corrections, settings=settings, on_llm_usage=on_usage,
        )

    def _run_agent_phase(self, project: ProjectRecord, phase: PhaseDef, record: PhaseRecord) -> StepResult:
        agent = self.agents[phase.agent]  # type: ignore[index]
        pid = project.id
        self._set_phase(record, PhaseStatus.ASSIGNED)
        record.attempts += 1
        record.started_at = utcnow().isoformat()
        self._set_phase(record, PhaseStatus.RUNNING)
        try:
            result = agent.run(phase.id, self._context(project, record))
        except UsageLimitError as e:
            self._set_phase(record, PhaseStatus.BLOCKED, error=f"Límite de uso de Claude: {e}", blocked_code="usage_limit")
            self._set_project_status(pid, ProjectStatus.BLOCKED, f"Límite de uso de Claude (reinicio: {e.resets_at or '?'})")
            return StepResult("usage_limit", phase.id, str(e), resets_at=e.resets_at)
        except AuthenticationError as e:
            self._set_phase(record, PhaseStatus.BLOCKED, error=f"Autenticación: {e}", blocked_code="auth")
            self._set_project_status(pid, ProjectStatus.BLOCKED, "Claude Code no autenticado: ejecuta `claude /login`")
            return StepResult("auth_error", phase.id, str(e))
        except PhaseBlocked as e:
            self._set_phase(record, PhaseStatus.BLOCKED, error=e.reason, blocked_code=e.code)
            self._set_project_status(pid, ProjectStatus.BLOCKED, e.reason)
            return StepResult("blocked", phase.id, e.reason)
        except (ProviderError, LLMError) as e:
            return self._fail(pid, record, str(e), retryable=getattr(e, "transient", False))
        except AcceptanceError as e:
            return self._fail(pid, record, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Fallo inesperado en %s/%s", pid, phase.id)
            return self._fail(pid, record, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

        record.finished_at = utcnow().isoformat()
        record.result = {"artifacts": result.artifacts, "metrics": result.metrics}
        record.scene_filter, record.corrections = None, []

        # ---- resultados que generan correcciones
        if phase.id == "corrections":
            plan = result.metrics.get("invalidate", [])
            if result.metrics.get("needs_human"):
                self._set_phase(record, PhaseStatus.COMPLETED, summary=result.summary)
                self.events.emit("project.needs_decision", project_id=pid, data={"summary": result.summary})
                return StepResult("ran", phase.id, result.summary)
            self._set_phase(record, PhaseStatus.COMPLETED, summary=result.summary)
            if plan:
                project = self.store.get_project(pid)
                project.correction_rounds += 1
                self.store.save_project(project)
                self._invalidate(pid, plan)
            return StepResult("ran", phase.id, result.summary)

        if result.corrections and phase.id != "review":
            # p. ej. la voz pide al guionista acortar escenas concretas.
            project = self.store.get_project(pid)
            if project.correction_rounds < self.settings.max_correction_rounds:
                from ..agents.chief import plan_invalidation
                project.correction_rounds += 1
                self.store.save_project(project)
                self._set_phase(record, PhaseStatus.COMPLETED, summary=result.summary)
                self._invalidate(pid, plan_invalidation(result.corrections), corrections=result.corrections)
                return StepResult("ran", phase.id, result.summary)

        # Las correcciones del revisor se guardan en review/latest.json y las gestiona la fase 'corrections'.
        self._set_phase(record, PhaseStatus.COMPLETED, summary=result.summary)
        return StepResult("ran", phase.id, result.summary)

    def _fail(self, pid: str, record: PhaseRecord, message: str, retryable: bool = False) -> StepResult:
        record.retryable = retryable
        self._set_phase(record, PhaseStatus.ERROR, error=message[:4000])
        self._set_project_status(pid, ProjectStatus.ERROR, message[:300])
        return StepResult("error", record.phase, message)

    def _invalidate(self, pid: str, plan: list[dict], corrections: list[CorrectionRequest] | None = None,
                    include_approvals: bool = False) -> None:
        """Devuelve a 'pending' las fases destino (con filtro de escenas) y sus dependientes."""
        targets = {p["phase"]: p for p in plan}
        affected: list[str] = []
        for phase_id in targets:
            affected += [phase_id] + downstream(phase_id)
        order = [p.id for p in PIPELINE]
        for phase_id in sorted(set(affected), key=order.index):
            rec = self.store.get_phase(pid, phase_id)
            pdef = PHASES[phase_id]
            if pdef.kind == "approval" and pdef.agent is None and rec.status is PhaseStatus.APPROVED \
                    and not include_approvals and phase_id == "script_approval":
                continue  # un guion aprobado no se vuelve a pedir por correcciones internas
            if phase_id in targets:
                scenes = targets[phase_id]["scenes"]
                rec.scene_filter = scenes
                rec.corrections = [c for c in (corrections or []) if c.phase == phase_id] or [
                    CorrectionRequest(target_agent=pdef.agent or "chief", phase=phase_id, scene_index=None, reason=r)
                    for r in targets[phase_id]["reasons"]
                ]
            elif phase_id in SCENE_SCOPED and all(t["scenes"] is not None for t in targets.values()):
                # Las fases por escena heredan el filtro: solo se rehacen las escenas afectadas.
                rec.scene_filter = sorted({i for t in targets.values() for i in t["scenes"]})
                rec.corrections = []
            else:
                # Resto de dependientes: se rehacen, pero los agentes reutilizan lo que no cambió (hashes).
                rec.scene_filter = None
                rec.corrections = []
            self._set_phase(rec, PhaseStatus.PENDING, summary="Invalidada por corrección")
        self.events.emit("project.corrections", project_id=pid, data={"plan": plan})

    def _set_phase(self, record: PhaseRecord, status: PhaseStatus, error: str | None = None,
                   summary: str | None = None, blocked_code: str | None = None) -> None:
        if status is not PhaseStatus.ERROR:
            record.retryable = False
        record.status = status
        record.error = error
        record.blocked_code = blocked_code
        if summary is not None:
            record.summary = summary
        self.store.save_phase(record)
        self.events.emit("phase.status", project_id=record.project_id, phase=record.phase,
                         agent=PHASES[record.phase].agent,
                         data={"status": status.value, "error": error, "summary": record.summary,
                               "attempts": record.attempts})
