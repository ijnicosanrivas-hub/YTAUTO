"""Modelos de línea temporal compartidos por voz, montaje, sonido y revisión."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..providers.interfaces import SubtitleCue


class VoiceScene(BaseModel):
    index: int
    path: str | None  # None si la escena no tiene narración
    voice_duration_s: float = 0.0
    start_s: float = 0.0  # inicio de la escena en la línea temporal final
    scene_duration_s: float
    planned_duration_s: float = 0.0  # duración prevista por el director (antes de ajustar a la voz)
    voice_offset_s: float = 0.15  # la voz empieza un poco después del corte
    text_hash: str = ""


class VoiceManifest(BaseModel):
    voice_id: str | None = None
    speed: float = 1.0
    scenes: list[VoiceScene]
    cues: list[SubtitleCue] = Field(default_factory=list)

    @property
    def total_duration_s(self) -> float:
        return round(sum(s.scene_duration_s for s in self.scenes), 3)

    def recompute_starts(self) -> None:
        t = 0.0
        for s in self.scenes:
            s.start_s = round(t, 3)
            t += s.scene_duration_s


class EditSegment(BaseModel):
    index: int
    path: str
    duration_s: float
    input_hash: str
    shots: int = 1  # sub-planos dentro de la escena (cambios visuales)


class EditManifest(BaseModel):
    segments: list[EditSegment]
    transitions: list[str]
    transition_s: float
    video_path: str
    duration_s: float
    cut_times_s: list[float] = Field(default_factory=list)


class SoundManifest(BaseModel):
    mix_path: str
    music_asset_id: str | None = None
    music_provider: str | None = None
    music_credit: str | None = None  # atribución obligatoria (p. ej. Creative Commons) para la descripción
    sfx: list[dict] = Field(default_factory=list)
    duration_s: float
