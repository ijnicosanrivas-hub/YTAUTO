"""Efectos de sonido locales: biblioteca con licencia y síntesis (numpy)."""
from __future__ import annotations

from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..audio_synth import SR, SUPPORTED_SFX, sfx, write_wav
from ..interfaces import HealthStatus, SFXRequest, SoundEffectsProvider
from ..library import AUDIO_EXT, best_match, default_library_root, scan
from ..music.local import audio_duration


class LocalLibrarySFXProvider(SoundEffectsProvider):
    """Efectos de la biblioteca local (library/sfx) por nombre/etiquetas."""
    name = "library_sfx"
    display_name = "Biblioteca local de efectos"
    default_priority = 10
    default_params = {"root": ""}

    @property
    def folder(self) -> Path:
        return Path(self.params["root"] or default_library_root()) / "sfx"

    def health_check(self) -> HealthStatus:
        n = len(scan(self.folder, AUDIO_EXT))
        return HealthStatus(ok=n > 0, message=f"{n} efectos con licencia" if n else f"Sin efectos en {self.folder}")

    def get_effect(self, request: SFXRequest) -> MediaAsset:
        item = best_match(scan(self.folder, AUDIO_EXT), request.effect.replace(":", " "), exclude=set())
        if item is None:
            raise ProviderError(self.name, f"Sin efecto '{request.effect}' en la biblioteca", transient=False)
        return MediaAsset(kind=AssetKind.AUDIO_SFX, path=str(item.path), duration_s=audio_duration(item.path),
                          provider=self.name, sha256=sha256_file(item.path), license=item.license,
                          source_url=item.meta.get("url"))


class SynthSFXProvider(SoundEffectsProvider):
    """Efectos sintetizados localmente: whoosh, impact, riser, pop, ambience, click. CC0."""
    name = "synth_sfx"
    display_name = "Efectos sintetizados (local)"
    default_priority = 90

    def capabilities(self):
        return {"effects": SUPPORTED_SFX, "cost": 0}

    def get_effect(self, request: SFXRequest) -> MediaAsset:
        kind = request.effect.split(":")[0].lower()
        if kind not in SUPPORTED_SFX:
            kind = "whoosh" if kind in ("swoosh", "transition", "swish") else (
                "impact" if kind in ("boom", "hit", "drop") else "pop")
        dur_tag = f"_{request.duration_s:.1f}" if request.duration_s else ""
        path = request.out_dir / f"sfx_{kind}{dur_tag}.wav"
        if not path.exists():
            data = sfx(kind, request.duration_s, seed=len(kind))
            write_wav(path, data)
        n_dur = audio_duration(path) or (len(sfx(kind, request.duration_s)) / SR)
        return MediaAsset(kind=AssetKind.AUDIO_SFX, path=str(path), duration_s=round(n_dur, 3), provider=self.name,
                          sha256=sha256_file(path),
                          license=License(name="generated", attribution="ytauto synth (CC0)", commercial_use=True),
                          metadata={"effect": kind})
