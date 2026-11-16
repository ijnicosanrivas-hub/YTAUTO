"""Perfiles de exportación por plataforma (config/platforms/*.yaml)."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..providers.interfaces import EncodeProfile, SubtitleStyle

PLATFORMS_DIR = Path(__file__).resolve().parents[3] / "config" / "platforms"


class MetadataLimits(BaseModel):
    title_max_chars: int
    description_max_chars: int
    hashtags_max: int
    title_required: bool = True


class PlatformProfile(BaseModel):
    id: str
    display_name: str
    min_duration_s: float
    max_duration_s: float
    encode: EncodeProfile
    subtitles: SubtitleStyle
    safe_area: dict[str, int]  # márgenes px: top, bottom, left, right
    metadata: MetadataLimits
    thumbnail: dict = Field(default_factory=dict)  # {supported: bool, width, height}
    verified_at: str | None = None
    docs: list[str] = Field(default_factory=list)
    notes: str = ""


def load_profiles(directory: Path | None = None) -> dict[str, PlatformProfile]:
    d = Path(directory or PLATFORMS_DIR)
    profiles = {}
    for f in sorted(d.glob("*.yaml")):
        p = PlatformProfile(**yaml.safe_load(f.read_text(encoding="utf-8")))
        profiles[p.id] = p
    return profiles
