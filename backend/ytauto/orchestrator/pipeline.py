"""Definición del flujo de producción: 18 fases con dependencias (DAG)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PhaseKind = Literal["auto", "claude", "media", "approval"]


@dataclass(frozen=True)
class PhaseDef:
    id: str
    number: int
    title: str
    agent: str | None
    kind: PhaseKind
    depends_on: tuple[str, ...] = ()
    queue: Literal["claude", "media", "none"] = "media"


PIPELINE: tuple[PhaseDef, ...] = (
    PhaseDef("intake", 1, "Introducción de la temática", "chief", "auto", (), "none"),
    PhaseDef("project_setup", 2, "Creación del proyecto", "chief", "auto", ("intake",), "none"),
    PhaseDef("creative_direction", 3, "Dirección creativa", "director", "claude", ("project_setup",), "claude"),
    PhaseDef("script", 4, "Guion", "scriptwriter", "claude", ("creative_direction",), "claude"),
    PhaseDef("script_approval", 5, "Aprobación del guion", None, "approval", ("script",), "none"),
    PhaseDef("scene_prep", 6, "Preparación de escenas", "resources", "claude", ("script_approval",), "claude"),
    PhaseDef("resource_generation", 7, "Generación de recursos", "resources", "media", ("scene_prep",), "media"),
    PhaseDef("voice", 8, "Locución", "voice", "media", ("script_approval",), "media"),
    PhaseDef("edit", 9, "Montaje", "editor", "media", ("resource_generation", "voice"), "media"),
    PhaseDef("sound", 10, "Música y efectos", "sound", "media", ("edit",), "media"),
    PhaseDef("render", 11, "Renderizado", "editor", "media", ("sound",), "media"),
    PhaseDef("review", 12, "Revisión", "reviewer", "claude", ("render",), "claude"),
    PhaseDef("corrections", 13, "Correcciones", "chief", "auto", ("review",), "none"),
    PhaseDef("final_approval", 14, "Aprobación final", None, "approval", ("corrections",), "none"),
    PhaseDef("exports", 15, "Exportaciones por plataforma", "publisher", "media", ("final_approval",), "media"),
    PhaseDef("publish_prep", 16, "Preparación de publicación", "publisher", "claude", ("exports",), "claude"),
    PhaseDef("publish", 17, "Publicación autorizada", "publisher", "approval", ("publish_prep",), "media"),
    PhaseDef("report", 18, "Informe final", "chief", "auto", ("publish",), "none"),
)

PHASES: dict[str, PhaseDef] = {p.id: p for p in PIPELINE}


def downstream(phase_id: str) -> list[str]:
    """Fases que dependen (transitivamente) de `phase_id`, en orden del flujo."""
    result: set[str] = set()
    frontier = {phase_id}
    while frontier:
        nxt = {p.id for p in PIPELINE if set(p.depends_on) & frontier} - result
        result |= nxt
        frontier = nxt
    return [p.id for p in PIPELINE if p.id in result]


def validate_pipeline() -> None:
    seen: set[str] = set()
    for p in PIPELINE:
        missing = set(p.depends_on) - seen
        if missing:
            raise ValueError(f"La fase {p.id} depende de fases posteriores o inexistentes: {missing}")
        seen.add(p.id)


validate_pipeline()
