"""Música local: biblioteca con licencia y generador procedural (numpy)."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..audio_synth import pick_mood, synth_music, write_wav
from ..interfaces import HealthStatus, MusicGenerationProvider, MusicRequest
from ..library import AUDIO_EXT, best_match, default_library_root, scan


def audio_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


class LocalLibraryMusicProvider(MusicGenerationProvider):
    """Pistas de la biblioteca local (library/music) elegidas por estado de ánimo/etiquetas."""
    name = "library_music"
    display_name = "Biblioteca local de música"
    default_priority = 10
    default_params = {"root": ""}

    @property
    def folder(self) -> Path:
        return Path(self.params["root"] or default_library_root()) / "music"

    def health_check(self) -> HealthStatus:
        n = len(scan(self.folder, AUDIO_EXT))
        return HealthStatus(ok=n > 0, message=f"{n} pistas con licencia" if n else f"Sin pistas en {self.folder}")

    def get_track(self, request: MusicRequest) -> MediaAsset:
        items = scan(self.folder, AUDIO_EXT)
        item = best_match(items, f"{request.mood} {request.genre or ''}", exclude=set(request.exclude_ids),
                          key=lambda i: i.path.name)
        if item is None:
            raise ProviderError(self.name, f"Sin pistas para '{request.mood}'", transient=False)
        return MediaAsset(kind=AssetKind.AUDIO_MUSIC, path=str(item.path), duration_s=audio_duration(item.path),
                          provider=self.name, sha256=sha256_file(item.path), license=item.license,
                          source_url=item.meta.get("url"), metadata={"library_tags": sorted(item.tags)})


class ProceduralMusicProvider(MusicGenerationProvider):
    """Música de fondo sintetizada localmente (pads, bajo, arpegio y pulso). CC0, sin coste."""
    name = "procedural_music"
    display_name = "Música procedural (local)"
    default_priority = 90
    default_params = {"bpm": 100}

    def capabilities(self):
        return {"moods": ["tense", "dark", "epic", "happy", "calm"], "loopable": True, "cost": 0}

    def get_track(self, request: MusicRequest) -> MediaAsset:
        mood = pick_mood(f"{request.mood} {request.genre or ''}")
        bpm = request.bpm or self.params["bpm"]
        seed = int(hashlib.sha256(f"{mood}|{bpm}|{request.duration_s:.0f}".encode()).hexdigest()[:8], 16)
        path = request.out_dir / f"music_{mood}_{bpm}_{int(request.duration_s)}.wav"
        if not path.exists():
            write_wav(path, synth_music(mood, request.duration_s + 1.0, bpm=bpm, seed=seed))
        return MediaAsset(kind=AssetKind.AUDIO_MUSIC, path=str(path), duration_s=round(request.duration_s + 1.0, 3),
                          provider=self.name, sha256=sha256_file(path),
                          license=License(name="generated", attribution="ytauto procedural (CC0)", commercial_use=True),
                          metadata={"mood": mood, "bpm": bpm})
