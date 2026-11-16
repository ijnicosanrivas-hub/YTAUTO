"""Perfiles de exportación por plataforma (config/platforms/*.yaml).

Cada perfil separa lo VERIFICADO con documentación oficial (con fecha y fuentes) de lo que
no lo está (`unverified`), para no presentar como oficial lo que es una recomendación.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from ..providers.interfaces import EncodeProfile, SubtitleStyle

PLATFORMS_DIR = Path(__file__).resolve().parents[3] / "config" / "platforms"


class FileLimits(BaseModel):
    """Requisitos técnicos del fichero según la plataforma."""

    containers: list[str] = Field(default_factory=lambda: ["mp4"])
    video_codecs: list[str] = Field(default_factory=lambda: ["h264"])
    audio_codecs: list[str] = Field(default_factory=lambda: ["aac"])
    pix_fmts: list[str] = Field(default_factory=lambda: ["yuv420p"])
    fps_min: float | None = None
    fps_max: float | None = None
    min_side: int | None = None  # px, lado menor/mayor mínimo
    max_side: int | None = None  # px, lado mayor máximo
    max_size_mb: float | None = None
    max_video_bitrate_mbps: float | None = None
    max_audio_sample_rate: int | None = None
    audio_channels: list[int] = Field(default_factory=lambda: [1, 2])
    require_moov_first: bool = False  # átomo moov al principio (+faststart)
    forbid_edit_lists: bool = False
    platform_min_duration_s: float | None = None
    platform_max_duration_s: float | None = None


class MetadataLimits(BaseModel):
    """Límites de título, descripción y etiquetas.

    mode:
      title_description → título + descripción + etiquetas aparte (YouTube).
      caption           → un único pie de texto con hashtags dentro (Instagram).
      title_caption     → el campo `title` es el pie de texto completo (TikTok).
    """

    mode: Literal["title_description", "caption", "title_caption"] = "title_description"
    title_max_chars: int = 100
    description_max_chars: int = 2200
    description_max_bytes: int | None = None  # YouTube mide la descripción en bytes UTF-8
    caption_max: int | None = None  # tope del pie compuesto (caption / title_caption)
    caption_unit: Literal["chars", "utf16"] = "chars"
    hashtags_max: int = 30
    tags_total_chars: int | None = None  # YouTube: suma de etiquetas (con comillas si llevan espacios)
    mentions_max: int | None = None
    title_required: bool = True


class PublishNotes(BaseModel):
    """Limitaciones conocidas de la vía oficial de publicación (para informar al usuario)."""

    public_url_required: bool = False
    unaudited_private_only: bool = False
    user_must_choose_privacy: bool = False
    daily_post_limit: int | None = None
    notes: list[str] = Field(default_factory=list)


class PlatformProfile(BaseModel):
    id: str
    display_name: str
    min_duration_s: float  # rango efectivo de EXPORTACIÓN (producto ∩ plataforma)
    max_duration_s: float
    encode: EncodeProfile
    subtitles: SubtitleStyle
    safe_area: dict[str, int]  # márgenes px: top, bottom, left, right
    metadata: MetadataLimits
    file: FileLimits = Field(default_factory=FileLimits)
    publish: PublishNotes = Field(default_factory=PublishNotes)
    thumbnail: dict = Field(default_factory=dict)  # {supported: bool, width, height}
    verified_at: str | None = None  # fecha de la última verificación con la documentación oficial
    sources: list[str] = Field(default_factory=list)  # URLs consultadas
    unverified: list[str] = Field(default_factory=list)  # campos que NO proceden de documentación oficial
    notes: str = ""

    @property
    def is_verified(self) -> bool:
        return bool(self.verified_at and self.sources)


def load_profiles(directory: Path | None = None) -> dict[str, PlatformProfile]:
    d = Path(directory or PLATFORMS_DIR)
    profiles = {}
    for f in sorted(d.glob("*.yaml")):
        p = PlatformProfile(**yaml.safe_load(f.read_text(encoding="utf-8")))
        profiles[p.id] = p
    return profiles
