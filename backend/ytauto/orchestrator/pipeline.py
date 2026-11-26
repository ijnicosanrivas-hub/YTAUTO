"""Definición del flujo de producción: 20 fases con dependencias (DAG)."""
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
    # El usuario elige gancho y enfoque ANTES del guion: corregir aquí cuesta una llamada, no un vídeo entero.
    PhaseDef("concept_approval", 4, "Aprobación del concepto y el gancho", None, "approval", ("creative_direction",), "none"),
    PhaseDef("script", 5, "Guion", "scriptwriter", "claude", ("concept_approval",), "claude"),
    PhaseDef("script_approval", 6, "Aprobación del guion", None, "approval", ("script",), "none"),
    PhaseDef("scene_prep", 7, "Preparación de escenas", "resources", "claude", ("script_approval",), "claude"),
    # Storyboard revisado antes de gastar créditos en imágenes o clips generados.
    PhaseDef("storyboard_approval", 8, "Aprobación del storyboard", None, "approval", ("scene_prep",), "none"),
    PhaseDef("resource_generation", 9, "Generación de recursos", "resources", "media", ("storyboard_approval",), "media"),
    PhaseDef("voice", 10, "Locución", "voice", "media", ("script_approval",), "media"),
    PhaseDef("edit", 11, "Montaje", "editor", "media", ("resource_generation", "voice"), "media"),
    PhaseDef("sound", 12, "Música y efectos", "sound", "media", ("edit",), "media"),
    PhaseDef("render", 13, "Renderizado", "editor", "media", ("sound",), "media"),
    PhaseDef("review", 14, "Revisión", "reviewer", "claude", ("render",), "claude"),
    PhaseDef("corrections", 15, "Correcciones", "chief", "auto", ("review",), "none"),
    PhaseDef("final_approval", 16, "Aprobación final", None, "approval", ("corrections",), "none"),
    PhaseDef("exports", 17, "Exportaciones por plataforma", "publisher", "media", ("final_approval",), "media"),
    PhaseDef("publish_prep", 18, "Preparación de publicación", "publisher", "claude", ("exports",), "claude"),
    PhaseDef("publish", 19, "Publicación autorizada", "publisher", "approval", ("publish_prep",), "media"),
    PhaseDef("report", 20, "Informe final", "chief", "auto", ("publish",), "none"),
)

# Puertas que se aprueban solas si el proyecto no las pide (modo automático), con el campo que las activa.
OPTIONAL_GATES: dict[str, str] = {
    "concept_approval": "require_concept_approval",
    "script_approval": "require_script_approval",
    "storyboard_approval": "require_storyboard_approval",
}
# Si el usuario rechaza una puerta, qué fase se rehace con su comentario.
REDO_ON_REJECT: dict[str, str] = {
    "concept_approval": "creative_direction",
    "script_approval": "script",
    "storyboard_approval": "scene_prep",
}

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
