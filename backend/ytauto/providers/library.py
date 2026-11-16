"""Biblioteca local de recursos con licencia (imágenes, vídeos, música, efectos).

Estructura:  library/<tipo>/<fichero>  +  licencia, de una de estas formas:
- fichero lateral `<fichero>.json`: {"license": "CC0", "attribution": "...", "url": "...",
  "tags": ["mar", "noche"], "commercial_use": true, "mood": "calm"}
- o un `licenses.json` en la carpeta con {"<fichero>": {...}, "*": {...por defecto...}}.

Los ficheros SIN licencia declarada se ignoran: no se usan recursos de procedencia desconocida.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from PIL import Image

from ..core.models import License
from ..core.settings import REPO_ROOT

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


def default_library_root() -> Path:
    import os
    p = Path(os.environ.get("YTAUTO_LIBRARY_DIR", "library"))
    return p if p.is_absolute() else REPO_ROOT / p


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(text)) if len(t) > 2}


class LibraryItem:
    def __init__(self, path: Path, meta: dict[str, Any]):
        self.path = path
        self.meta = meta
        self.tags = tokens(path.stem.replace("_", " ").replace("-", " ")) | tokens(" ".join(meta.get("tags", [])))
        if meta.get("mood"):
            self.tags |= tokens(str(meta["mood"]))

    @property
    def license(self) -> License:
        return License(name=self.meta.get("license", "unknown"), attribution=self.meta.get("attribution"),
                       url=self.meta.get("url"), commercial_use=self.meta.get("commercial_use"))

    def score(self, query: str) -> int:
        return len(self.tags & tokens(query))


def scan(folder: Path, extensions: set[str]) -> list[LibraryItem]:
    if not folder.exists():
        return []
    shared = {}
    lic_file = folder / "licenses.json"
    if lic_file.exists():
        shared = json.loads(lic_file.read_text(encoding="utf-8"))
    items = []
    for f in sorted(folder.rglob("*")):
        if f.suffix.lower() not in extensions or not f.is_file():
            continue
        side = f.with_name(f.name + ".json")
        meta = json.loads(side.read_text(encoding="utf-8")) if side.exists() else (
            shared.get(f.name) or shared.get("*"))
        if not meta or not meta.get("license"):
            continue  # sin licencia declarada → no se usa
        items.append(LibraryItem(f, meta))
    return items


def average_hash(path: Path) -> str:
    """Hash perceptual sencillo (aHash 8x8) para detectar imágenes repetidas."""
    with Image.open(path) as im:
        small = im.convert("L").resize((8, 8))
        px = list(small.tobytes())
    avg = sum(px) / len(px)
    bits = "".join("1" if p >= avg else "0" for p in px)
    return f"{int(bits, 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def best_match(items: list[LibraryItem], query: str, exclude: set[str], key=lambda i: str(i.path)) -> LibraryItem | None:
    ranked = sorted((i for i in items if key(i) not in exclude), key=lambda i: (-i.score(query), str(i.path)))
    return ranked[0] if ranked and ranked[0].score(query) > 0 else None
