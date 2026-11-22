"""Canales: cada uno agrupa proyectos, un perfil visual (tema) y sus licencias de Claude."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from .settings import REPO_ROOT

CHANNELS_FILE = REPO_ROOT / "config" / "channels.yaml"
DEFAULT_CHANNEL = "general"
_ID = re.compile(r"^[a-z0-9_-]{1,32}$")


class Channel(BaseModel):
    id: str
    name: str
    theme: str
    tagline: str = ""

    @field_validator("id", "theme")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError(f"identificador no válido: {v!r}")
        return v


def load_channels(path: Path | None = None) -> list[Channel]:
    """Canales configurados; si falta el fichero, un único canal «General» (nunca rompe la app)."""
    path = path or CHANNELS_FILE
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        out = [Channel.model_validate(c) for c in data.get("channels", [])]
    except (OSError, ValueError, yaml.YAMLError):
        out = []
    seen: set[str] = set()
    out = [c for c in out if not (c.id in seen or seen.add(c.id))]  # sin duplicados
    return out or [Channel(id=DEFAULT_CHANNEL, name="General", theme="gotham")]


@lru_cache(maxsize=1)
def channels() -> tuple[Channel, ...]:
    return tuple(load_channels())


def channel_ids() -> set[str]:
    return {c.id for c in channels()}
