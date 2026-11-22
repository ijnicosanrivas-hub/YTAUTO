"""Modelos de dominio comunes. No dependen de ningún proveedor ni del motor LLM."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MIN_DURATION_S = 45
MAX_DURATION_S = 75


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ERROR = "error"
    IN_REVIEW = "in_review"
    APPROVED = "approved"

    @property
    def is_done(self) -> bool:
        return self in (PhaseStatus.COMPLETED, PhaseStatus.APPROVED)


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ERROR = "error"


class Platform(str, Enum):
    INSTAGRAM_REELS = "instagram_reels"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"


class Section(str, Enum):
    HOOK = "hook"
    CONTEXT = "context"
    DEVELOPMENT = "development"
    CLIMAX = "climax"
    CLOSING = "closing"


Intensity = Literal["low", "medium", "high"]


class BriefAnswer(BaseModel):
    """Una pregunta del director antes de empezar y la respuesta del usuario."""

    question: str
    answer: str = ""


class ProjectSpec(BaseModel):
    """Lo que introduce el usuario en el formulario de creación."""

    name: str
    topic: str
    idea: str = ""
    duration_s: int = 60
    visual_style: str | None = None
    narration_type: str | None = None  # p. ej. "narrador en off", "primera persona"
    language: str = "es"
    voice_type: str | None = None
    music: str | None = None
    intensity: Intensity = "medium"
    subtitle_mode: Literal["karaoke", "word_pop", "line"] | None = None  # None = el del perfil de plataforma
    platforms: list[Platform] = Field(
        default_factory=lambda: [Platform.YOUTUBE_SHORTS, Platform.INSTAGRAM_REELS, Platform.TIKTOK]
    )
    preferred_providers: dict[str, str] = Field(default_factory=dict)
    budget_max_eur: float = 0.0
    mode: Literal["auto", "custom"] = "auto"
    fps: int = 30
    require_script_approval: bool = True
    channel: str = "general"  # canal al que pertenece (config/channels.yaml)
    brief: list[BriefAnswer] = Field(default_factory=list)  # preguntas del director y respuestas
    license_map: dict[str, str] = Field(default_factory=dict)  # agente → licencia de Claude elegida

    @field_validator("duration_s")
    @classmethod
    def _duration_in_range(cls, v: int) -> int:
        if not MIN_DURATION_S <= v <= MAX_DURATION_S:
            raise ValueError(f"La duración debe estar entre {MIN_DURATION_S} y {MAX_DURATION_S} s")
        return v

    @field_validator("fps")
    @classmethod
    def _fps_valid(cls, v: int) -> int:
        if v not in (24, 25, 30, 50, 60):
            raise ValueError("FPS admitidos: 24, 25, 30, 50, 60")
        return v

    @field_validator("budget_max_eur")
    @classmethod
    def _budget_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El presupuesto no puede ser negativo")
        return v


# ---------- Dirección creativa ----------


class ScenePlan(BaseModel):
    index: int
    section: Section
    duration_s: float
    purpose: str
    visual_direction: str
    camera_motion: str = "slow_zoom_in"
    transition: str = "cut"
    on_screen_text: str | None = None
    sfx: list[str] = Field(default_factory=list)


class CreativeBrief(BaseModel):
    concept: str
    tone: str
    visual_style: str
    palette: list[str] = Field(default_factory=list)
    pacing: str
    target_duration_s: int
    music_direction: str
    scenes: list[ScenePlan]
    resource_needs: list[str] = Field(default_factory=list)


# ---------- Guion ----------


class ScriptScene(BaseModel):
    index: int
    section: Section
    duration_s: float
    narration: str
    dialogue: list[str] = Field(default_factory=list)
    visual_notes: str
    sfx: list[str] = Field(default_factory=list)
    music_cue: str | None = None
    subtitle_lines: list[str] = Field(default_factory=list)


class Script(BaseModel):
    internal_title: str
    topic: str
    narrative_goal: str
    hook: str
    closing: str
    call_to_action: str | None = None
    music: str
    scenes: list[ScriptScene]

    @property
    def total_duration_s(self) -> float:
        return round(sum(s.duration_s for s in self.scenes), 2)

    @property
    def total_words(self) -> int:
        return sum(len(s.narration.split()) for s in self.scenes)


# ---------- Recursos ----------


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO_VOICE = "audio_voice"
    AUDIO_MUSIC = "audio_music"
    AUDIO_SFX = "audio_sfx"
    AUDIO_MIX = "audio_mix"
    SUBTITLES = "subtitles"
    VIDEO_SEGMENT = "video_segment"
    VIDEO_MASTER = "video_master"
    VIDEO_EXPORT = "video_export"
    THUMBNAIL = "thumbnail"


class License(BaseModel):
    name: str = "unknown"  # "CC0", "CC-BY-4.0", "generated", "proprietary", ...
    attribution: str | None = None
    url: str | None = None
    commercial_use: bool | None = None


class MediaAsset(BaseModel):
    """Modelo interno común: idéntico venga del proveedor que venga."""

    id: str = Field(default_factory=lambda: new_id("ast_"))
    kind: AssetKind
    path: str
    sha256: str | None = None
    perceptual_hash: str | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    provider: str
    prompt: str | None = None
    source_url: str | None = None
    license: License = Field(default_factory=License)
    cost_eur: float = 0.0
    project_id: str | None = None
    scene_index: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class ScenePrompt(BaseModel):
    scene_index: int
    kind: Literal["image", "video"] = "image"
    prompt: str
    search_query: str
    negative_prompt: str | None = None
    style_tags: list[str] = Field(default_factory=list)


class CorrectionRequest(BaseModel):
    target_agent: str
    phase: str
    scene_index: int | None = None
    reason: str
    severity: Literal["minor", "major", "critical"] = "major"
