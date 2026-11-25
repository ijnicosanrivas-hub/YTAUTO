"""Importar pistas descargadas de la Biblioteca de audio de YouTube Studio (no hay API: se descargan a mano).

Cada pista se guarda en `library/youtube_audio_library/` con su ficha (`<pista>.json`): título, artista, género,
estado de ánimo y licencia. Las de Creative Commons exigen el texto de atribución que da YouTube Studio.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..app import App
from ..providers.music import youtube_audio_library as yal

MAX_MB = 30
EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


class TrackMeta(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    artist: str | None = Field(default=None, max_length=200)
    genre: str | None = Field(default=None, max_length=60)
    mood: str | None = Field(default=None, max_length=60)
    attribution_required: bool | None = None
    attribution: str | None = Field(default=None, max_length=1000)


class TrackIn(TrackMeta):
    filename: str = Field(min_length=1, max_length=200)
    data_b64: str = Field(min_length=8)


def safe_name(filename: str) -> str:
    """Nombre de fichero seguro (sin rutas ni caracteres raros), conservando la extensión."""
    base = Path(filename.replace("\\", "/")).name
    stem, ext = Path(base).stem, Path(base).suffix.lower()
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9 ._()&'-]+", "", stem).strip(" .")[:120] or "pista"
    return f"{stem}{ext}"


def guess_title_artist(filename: str) -> tuple[str, str | None]:
    """«Título - Artista.mp3» (así nombra YouTube Studio muchas descargas) → (título, artista). Es solo una pista."""
    stem = Path(filename).stem.replace("_", " ").strip()
    if " - " in stem:
        title, artist = stem.split(" - ", 1)
        return title.strip(), artist.strip() or None
    return stem, None


def register(api: FastAPI, app: App, deps: list) -> None:
    A = deps

    def folder() -> Path:
        return yal.library_folder()

    def track_path(name: str) -> Path:
        p = folder() / safe_name(name)
        if p.suffix.lower() not in EXT or not p.is_file():
            raise HTTPException(404, "Pista inexistente")
        return p

    def view(p: Path) -> dict[str, Any]:
        side = p.with_name(p.name + ".json")
        meta = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
        return {"file": p.name, "size_mb": round(p.stat().st_size / 1e6, 2), "title": meta.get("title"),
                "artist": meta.get("artist"), "genre": meta.get("genre"), "mood": meta.get("mood"),
                "license": meta.get("license"), "attribution_required": yal.attribution_required(meta),
                "attribution": meta.get("attribution"), "duration_s": meta.get("duration_s"),
                "usable": bool(meta.get("license"))}

    def write_meta(p: Path, meta: dict[str, Any]) -> None:
        required = bool(meta.get("attribution_required"))
        if required and not (meta.get("attribution") or "").strip():
            raise HTTPException(400, "Esta pista exige atribución: pega el texto que da YouTube Studio "
                                     "(columna «License type» → icono de Creative Commons → Copy)")
        meta["license"] = "Creative Commons (YouTube Audio Library)" if required else "YouTube Audio Library"
        meta["commercial_use"] = True
        meta["source"] = "youtube_audio_library"
        meta["url"] = yal.AUDIO_LIBRARY_URL
        meta["tags"] = [t for t in (meta.get("genre"), meta.get("mood")) if t]
        p.with_name(p.name + ".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @api.get("/api/music/youtube", dependencies=A)
    def list_tracks():
        d = folder()
        tracks = [view(p) for p in sorted(d.iterdir()) if p.suffix.lower() in EXT and p.is_file()] if d.is_dir() else []
        return {"tracks": tracks, "genres": yal.GENRES, "moods": yal.MOODS, "folder": str(d),
                "audio_library_url": yal.AUDIO_LIBRARY_URL, "help_url": yal.HELP_URL}

    @api.post("/api/music/youtube", dependencies=A, status_code=201)
    def import_track(body: TrackIn):
        name = safe_name(body.filename)
        if Path(name).suffix not in EXT:
            raise HTTPException(400, "Formato no admitido (usa el MP3 que descarga YouTube Studio)")
        try:
            raw = base64.b64decode(body.data_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(400, "Archivo dañado") from e
        if len(raw) > MAX_MB * 1024 * 1024:
            raise HTTPException(413, f"La pista supera {MAX_MB} MB")
        if len(raw) < 1024:
            raise HTTPException(400, "El archivo está vacío o no es audio")
        d = folder()
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        title, artist = guess_title_artist(name)
        meta = {"title": body.title or title, "artist": body.artist or artist, "genre": body.genre, "mood": body.mood,
                "attribution_required": bool(body.attribution_required), "attribution": body.attribution}
        p.write_bytes(raw)
        try:
            write_meta(p, meta)
        except HTTPException:
            p.unlink(missing_ok=True)
            raise
        from ..providers.music.local import audio_duration
        dur = audio_duration(p)
        if dur <= 0:
            p.unlink(missing_ok=True)
            p.with_name(p.name + ".json").unlink(missing_ok=True)
            raise HTTPException(400, "No se pudo leer el audio (¿es el MP3 de YouTube Studio?)")
        meta["duration_s"] = round(dur, 1)
        write_meta(p, meta)
        return view(p)

    @api.patch("/api/music/youtube/{name}", dependencies=A)
    def edit_track(name: str, body: TrackMeta):
        p = track_path(name)
        side = p.with_name(p.name + ".json")
        meta = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
        meta.update(body.model_dump(exclude_unset=True))
        write_meta(p, meta)
        return view(p)

    @api.delete("/api/music/youtube/{name}", dependencies=A)
    def delete_track(name: str):
        p = track_path(name)
        p.unlink()
        p.with_name(p.name + ".json").unlink(missing_ok=True)
        return {"ok": True}


