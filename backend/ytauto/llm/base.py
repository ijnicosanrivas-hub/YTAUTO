"""Interfaz del motor de inteligencia. Los agentes solo conocen esta interfaz."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from ..core.errors import YtautoError


class LLMError(YtautoError):
    """Error genérico (posiblemente transitorio) del motor LLM."""

    transient = True


class UsageLimitError(LLMError):
    """Se alcanzó el límite de uso de la suscripción. La cola debe pausarse."""

    transient = False

    def __init__(self, message: str, resets_at: str | None = None, license_id: str | None = None):
        self.resets_at = resets_at
        self.license_id = license_id  # licencia agotada (None = la sesión única por defecto)
        super().__init__(message)


class AuthenticationError(LLMError):
    """La sesión de Claude Code no está autenticada (ejecuta `claude /login`)."""

    transient = False


class ModelUnavailableError(LLMError):
    """El modelo solicitado no está disponible para esta cuenta."""

    transient = False


class LLMRequest(BaseModel):
    agent: str
    model: str = "sonnet"
    task: str  # instrucción concreta de esta tarea
    context: dict[str, Any] = Field(default_factory=dict)  # datos estructurados de entrada
    output_schema: dict[str, Any]  # JSON Schema de la salida esperada
    feedback: list[str] = Field(default_factory=list)  # fallos del intento anterior
    project_id: str | None = None  # para elegir la licencia asignada (no se envía a Claude)


class LLMUsage(BaseModel):
    duration_s: float = 0.0
    model_served: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_equivalent: float | None = None  # indicador informativo, NO factura
    num_turns: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    license_id: str | None = None  # licencia que atendió la llamada


class LLMResponse(BaseModel):
    data: dict[str, Any]
    raw_text: str = ""
    usage: LLMUsage = Field(default_factory=LLMUsage)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Ejecuta una tarea y devuelve un objeto JSON que cumple `output_schema`."""

    def health_check(self) -> tuple[bool, str]:
        return True, "ok"


def render_prompt(request: LLMRequest) -> str:
    """Convierte una petición en el texto que recibe Claude (usado por el adaptador CLI)."""
    import json

    parts = [
        "## Tarea",
        request.task.strip(),
        "",
        "## Datos de entrada (JSON)",
        json.dumps(request.context, ensure_ascii=False, indent=2, default=str),
        "",
        "## Formato de salida",
        "Responde ÚNICAMENTE con un objeto JSON válido que cumpla este JSON Schema, sin texto adicional:",
        json.dumps(request.output_schema, ensure_ascii=False),
    ]
    if request.feedback:
        parts += [
            "",
            "## Correcciones obligatorias",
            "Tu respuesta anterior fue rechazada por estos motivos. Corrígelos:",
            *[f"- {f}" for f in request.feedback],
        ]
    return "\n".join(parts)
