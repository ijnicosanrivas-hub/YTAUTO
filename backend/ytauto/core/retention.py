"""Comprobaciones de retención para vídeo corto, calculadas con datos reales del montaje.

Miden lo que el código puede verificar con certeza (tiempos, cambios visuales, huecos);
la calidad del gancho como texto la evalúa el revisor editorial (Claude).
"""
from __future__ import annotations

from pydantic import BaseModel

from .narrative import NarrativeTemplate
from .timeline import EditManifest, VoiceManifest

HOOK_TOLERANCE_S = 0.6
FIRST_VOICE_MAX_S = 0.5
MAX_DEAD_AIR_S = 1.5


class QualityCheck(BaseModel):
    name: str
    passed: bool
    points: float
    max_points: float
    detail: str = ""
    target_agent: str | None = None
    scene_index: int | None = None
    critical: bool = False  # un fallo crítico impide aprobar aunque la nota supere el umbral


def _check(name: str, passed: bool, max_points: float, detail: str, target: str | None,
           scene: int | None = None) -> QualityCheck:
    return QualityCheck(name=name, passed=passed, points=max_points if passed else 0.0, max_points=max_points,
                        detail=detail, target_agent=target, scene_index=scene)


def retention_checks(voice: VoiceManifest, edit: EditManifest, narrative: NarrativeTemplate,
                     intensity: str) -> list[QualityCheck]:
    out: list[QualityCheck] = []
    first = voice.scenes[0] if voice.scenes else None
    hook_s = first.scene_duration_s if first else 0.0
    out.append(_check("gancho ≤ 3 s", hook_s <= narrative.hook_max_s + HOOK_TOLERANCE_S, 4,
                      f"primera escena {hook_s:.2f}s", "scriptwriter", 0))
    first_voice = (first.start_s + first.voice_offset_s) if first and first.path else None
    out.append(_check("voz desde el inicio", first_voice is not None and first_voice <= FIRST_VOICE_MAX_S, 3,
                      f"primera palabra en {first_voice:.2f}s" if first_voice is not None else "el gancho no tiene voz",
                      "voice"))
    gaps = [(s.index, s.scene_duration_s - s.voice_offset_s - s.voice_duration_s) for s in voice.scenes if s.path]
    worst = max(gaps, key=lambda g: g[1], default=(None, 0.0))
    out.append(_check("sin tiempos muertos", worst[1] <= MAX_DEAD_AIR_S, 4,
                      f"mayor hueco sin voz {worst[1]:.2f}s (escena {worst[0]})", "scriptwriter", worst[0]))
    max_static = narrative.max_static_shot_s[intensity]
    longest_shot = max((seg.duration_s / max(1, seg.shots) for seg in edit.segments), default=0.0)
    out.append(_check("cambios visuales frecuentes", longest_shot <= max_static + 0.35, 4,
                      f"plano más largo {longest_shot:.2f}s (máx {max_static}s, intensidad {intensity})", "editor"))
    return out
