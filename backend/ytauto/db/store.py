"""Implementación SQLite del puerto `StateStore` del orquestador."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from ..core.events import Event
from ..core.models import CorrectionRequest, PhaseStatus, ProjectSpec, ProjectStatus, utcnow
from ..orchestrator.pipeline import PIPELINE
from ..orchestrator.state import Approval, PhaseRecord, ProjectRecord, StateStore
from . import schema as s


class SqlStateStore(StateStore):
    def __init__(self, engine: Engine):
        self.engine = engine
        s.init_db(engine)

    # ------------------------------------------------------------------ proyectos
    def create_project(self, record: ProjectRecord) -> None:
        with self.engine.begin() as c:
            if c.execute(select(s.projects.c.id).where(s.projects.c.id == record.id)).first():
                raise ValueError(f"Proyecto duplicado: {record.id}")
            c.execute(insert(s.projects).values(**self._project_row(record)))
            c.execute(insert(s.phases), [self._phase_row(PhaseRecord(project_id=record.id, phase=p.id))
                                         for p in PIPELINE])

    def get_project(self, project_id: str) -> ProjectRecord:
        with self.engine.connect() as c:
            row = c.execute(select(s.projects).where(s.projects.c.id == project_id)).mappings().first()
        if row is None:
            raise KeyError(project_id)
        return self._project_from(row)

    def save_project(self, record: ProjectRecord) -> None:
        record.updated_at = utcnow().isoformat()
        with self.engine.begin() as c:
            c.execute(update(s.projects).where(s.projects.c.id == record.id).values(**self._project_row(record)))

    def list_projects(self) -> list[ProjectRecord]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.projects).order_by(s.projects.c.created_at.desc())).mappings().all()
        return [self._project_from(r) for r in rows]

    def delete_project(self, project_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(s.projects.delete().where(s.projects.c.id == project_id))

    # ------------------------------------------------------------------ fases
    def get_phase(self, project_id: str, phase: str) -> PhaseRecord:
        with self.engine.connect() as c:
            row = c.execute(select(s.phases).where(s.phases.c.project_id == project_id,
                                                   s.phases.c.phase == phase)).mappings().first()
        if row is None:
            raise KeyError((project_id, phase))
        return self._phase_from(row)

    def save_phase(self, record: PhaseRecord) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.phases).where(s.phases.c.project_id == record.project_id,
                                             s.phases.c.phase == record.phase).values(**self._phase_row(record)))

    def list_phases(self, project_id: str) -> list[PhaseRecord]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.phases).where(s.phases.c.project_id == project_id)).mappings().all()
        by = {r["phase"]: self._phase_from(r) for r in rows}
        return [by[p.id] for p in PIPELINE if p.id in by]

    # ------------------------------------------------------------------ aprobaciones
    def add_approval(self, approval: Approval) -> Approval:
        approval.id = approval.id or f"apr_{uuid.uuid4().hex[:10]}"
        with self.engine.begin() as c:
            c.execute(insert(s.approvals).values(**approval.model_dump()))
        return approval

    def get_approvals(self, project_id: str) -> list[Approval]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.approvals).where(s.approvals.c.project_id == project_id)
                             .order_by(s.approvals.c.at)).mappings().all()
        return [Approval(**dict(r)) for r in rows]

    # ------------------------------------------------------------------ consumo Claude
    def record_llm_usage(self, project_id: str, agent: str, phase: str, usage: dict[str, Any]) -> None:
        with self.engine.begin() as c:
            c.execute(insert(s.llm_usage).values(project_id=project_id, agent=agent, phase=phase,
                                                 at=utcnow().isoformat(), data=usage))

    def llm_usage(self, project_id: str | None = None) -> list[dict[str, Any]]:
        q = select(s.llm_usage)
        if project_id:
            q = q.where(s.llm_usage.c.project_id == project_id)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.llm_usage.c.id)).mappings().all()
        return [{"project_id": r["project_id"], "agent": r["agent"], "phase": r["phase"], "at": r["at"],
                 **(r["data"] or {})} for r in rows]

    # ------------------------------------------------------------------ registro de actividad
    def log_event(self, e: Event) -> None:
        with self.engine.begin() as c:
            c.execute(insert(s.events_log).values(type=e.type, project_id=e.project_id, agent=e.agent,
                                                  phase=e.phase, data=e.data, at=e.at))

    def events(self, project_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        q = select(s.events_log)
        if project_id:
            q = q.where(s.events_log.c.project_id == project_id)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.events_log.c.id.desc()).limit(limit)).mappings().all()
        return [dict(r) for r in reversed(rows)]

    # ------------------------------------------------------------------ conversión
    @staticmethod
    def _project_row(r: ProjectRecord) -> dict[str, Any]:
        return {"id": r.id, "name": r.spec.name, "spec": r.spec.model_dump(mode="json"), "status": r.status.value,
                "correction_rounds": r.correction_rounds, "blocked_reason": r.blocked_reason,
                "created_at": r.created_at, "updated_at": r.updated_at}

    @staticmethod
    def _project_from(row) -> ProjectRecord:
        return ProjectRecord(id=row["id"], spec=ProjectSpec.model_validate(row["spec"]),
                             status=ProjectStatus(row["status"]), correction_rounds=row["correction_rounds"],
                             blocked_reason=row["blocked_reason"], created_at=row["created_at"],
                             updated_at=row["updated_at"])

    @staticmethod
    def _phase_row(r: PhaseRecord) -> dict[str, Any]:
        return {"project_id": r.project_id, "phase": r.phase, "status": r.status.value, "attempts": r.attempts,
                "error": r.error, "blocked_code": r.blocked_code, "retryable": r.retryable, "summary": r.summary,
                "result": r.result, "scene_filter": r.scene_filter,
                "corrections": [c.model_dump(mode="json") for c in r.corrections],
                "started_at": r.started_at, "finished_at": r.finished_at}

    @staticmethod
    def _phase_from(row) -> PhaseRecord:
        return PhaseRecord(project_id=row["project_id"], phase=row["phase"], status=PhaseStatus(row["status"]),
                           attempts=row["attempts"], error=row["error"], blocked_code=row["blocked_code"],
                           retryable=bool(row["retryable"]), summary=row["summary"], result=row["result"] or {},
                           scene_filter=row["scene_filter"],
                           corrections=[CorrectionRequest.model_validate(c) for c in (row["corrections"] or [])],
                           started_at=row["started_at"], finished_at=row["finished_at"])
