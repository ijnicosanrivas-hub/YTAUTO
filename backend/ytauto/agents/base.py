"""Contrato común de los nueve agentes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError

from ..core.errors import AcceptanceError
from ..core.events import EventBus
from ..core.models import CorrectionRequest, ProjectSpec
from ..core.narrative import NarrativeTemplate
from ..core.workspace import ProjectMemory, Workspace
from ..llm.base import LLMProvider, LLMRequest, LLMUsage, ModelUnavailableError
from ..providers.interfaces import ProviderGateway

T = TypeVar("T", bound=BaseModel)

MODELS_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "models" / "models.yaml"


class ModelConfig(BaseModel):
    default: str = "sonnet"
    fallback: str = "sonnet"
    agents: dict[str, str] = Field(default_factory=dict)
    concurrency: int = 1
    max_concurrency: int = 2
    timeout_s: int = 600

    @classmethod
    def load(cls, path: Path | None = None) -> "ModelConfig":
        p = Path(path or MODELS_CONFIG_PATH)
        return cls(**yaml.safe_load(p.read_text(encoding="utf-8"))) if p.exists() else cls()

    def apply_overrides(self, overrides: dict | None) -> "ModelConfig":
        """Aplica en caliente los cambios hechos desde el panel 'Modelos Claude'."""
        if not overrides:
            return self
        for key in ("default", "fallback"):
            if overrides.get(key):
                setattr(self, key, overrides[key])
        self.agents.update(overrides.get("agents") or {})
        return self

    def for_agent(self, agent: str) -> str:
        return self.agents.get(agent, self.default)


@dataclass
class AgentContext:
    project_id: str
    spec: ProjectSpec
    workspace: Workspace
    memory: ProjectMemory
    llm: LLMProvider
    providers: ProviderGateway
    models: ModelConfig
    narrative: NarrativeTemplate
    events: EventBus
    # Si se indica, el agente solo rehace estas escenas (render incremental / correcciones).
    scene_filter: set[int] | None = None
    corrections: list[CorrectionRequest] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    on_llm_usage: Callable[[str, str, LLMUsage], None] | None = None

    def wants_scene(self, index: int) -> bool:
        return self.scene_filter is None or index in self.scene_filter


class AgentResult(BaseModel):
    status: str = "completed"  # completed | in_review | blocked
    summary: str
    artifacts: dict[str, str] = Field(default_factory=dict)  # nombre lógico -> ruta
    corrections: list[CorrectionRequest] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class Agent(ABC):
    name: str
    title: str
    phases: frozenset[str]
    uses_claude: bool = False

    def run(self, phase: str, ctx: AgentContext) -> AgentResult:
        if phase not in self.phases:
            raise ValueError(f"El agente {self.name} no ejecuta la fase {phase}")
        ctx.events.emit("agent.started", project_id=ctx.project_id, agent=self.name, phase=phase)
        result = self.execute(phase, ctx)
        ctx.memory.set_summary(phase, result.summary)
        ctx.events.emit(
            "agent.finished", project_id=ctx.project_id, agent=self.name, phase=phase,
            data={"status": result.status, "summary": result.summary, "metrics": result.metrics},
        )
        return result

    @abstractmethod
    def execute(self, phase: str, ctx: AgentContext) -> AgentResult: ...

    # ------------------------------------------------------------------ utilidades

    def progress(self, ctx: AgentContext, phase: str, value: float, message: str = "") -> None:
        ctx.events.emit(
            "agent.progress", project_id=ctx.project_id, agent=self.name, phase=phase,
            data={"progress": round(max(0.0, min(1.0, value)), 3), "message": message},
        )

    def ask_llm(
        self,
        ctx: AgentContext,
        *,
        phase: str,
        task: str,
        context: dict[str, Any],
        output_model: type[T],
        accept: Callable[[T], list[str]] | None = None,
        advise: Callable[[T], list[str]] | None = None,
        max_attempts: int = 2,
        schema: dict[str, Any] | None = None,
    ) -> T:
        """Pide a Claude una salida estructurada y la valida con código.

        - `accept`: criterios DUROS. Si no se cumplen se reintenta con el detalle de los fallos (máx.
          `max_attempts`) y, si persisten, AcceptanceError.
        - `advise`: criterios SUAVES (calidad, no corrección). Se usan para pedir una mejora en el reintento, pero
          una salida válida que solo incumple avisos se ACEPTA al agotar los intentos (con una nota en la memoria):
          un déficit pequeño no debe tirar toda la producción. Si un reintento posterior fallara en lo duro, se
          conserva la mejor salida válida anterior.
        """
        model = ctx.models.for_agent(self.name)
        feedback: list[str] = []
        schema = schema or output_model.model_json_schema()
        full_context = {**context, "project_memory": ctx.memory.digest()}
        best_soft: T | None = None
        soft_notes: list[str] = []
        for attempt in range(1, max_attempts + 1):
            request = LLMRequest(
                agent=self.name, model=model, task=task, context=full_context,
                output_schema=schema, feedback=feedback,
            )
            ctx.events.emit(
                "llm.call", project_id=ctx.project_id, agent=self.name, phase=phase,
                data={"model": model, "attempt": attempt,
                      # Por qué se reintenta (visible en el historial): permite diagnosticar con datos reales.
                      **({"retry_reason": [f[:200] for f in feedback[:3]]} if feedback else {})},
            )
            try:
                response = ctx.llm.complete(request)
            except ModelUnavailableError:
                if model == ctx.models.fallback:
                    raise
                ctx.memory.add_decision(self.name, f"Modelo '{model}' no disponible; uso '{ctx.models.fallback}'")
                model = ctx.models.fallback
                response = ctx.llm.complete(request.model_copy(update={"model": model}))
            if ctx.on_llm_usage:
                ctx.on_llm_usage(self.name, phase, response.usage)
            try:
                parsed = output_model.model_validate(response.data)
            except ValidationError as e:
                feedback = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()][:15]
                continue
            issues = accept(parsed) if accept else []
            if not issues:
                advice = advise(parsed) if advise else []
                if not advice:
                    return parsed
                best_soft, soft_notes = parsed, advice  # válida, pero mejorable
                if attempt == max_attempts:
                    break
                feedback = advice
                continue
            feedback = issues
        if best_soft is not None:
            ctx.memory.add_decision(self.name, "Aceptado con aviso tras agotar los intentos: " + "; ".join(soft_notes))
            return best_soft
        raise AcceptanceError(self.name, feedback)
