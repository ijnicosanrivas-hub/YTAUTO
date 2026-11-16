"""Voz neuronal local con Piper (gratuita, sin red durante el uso).

Requiere `pip install piper-tts` y un modelo de voz (.onnx + .onnx.json) en `model_dir`
(por defecto `data/models/piper`). Descarga de modelos (una vez, en tu equipo):

    python -m piper.download_voices es_ES-davefx-medium --data-dir data/models/piper

Revisa la licencia de cada voz en su ficha (MODEL_CARD) antes de un uso comercial.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

from ...core.errors import ProviderError, ProviderNotConfigured
from ...core.models import AssetKind, License, MediaAsset
from ...core.settings import REPO_ROOT
from ..interfaces import HealthStatus, TextToSpeechProvider, TTSRequest, Voice


class PiperTTSProvider(TextToSpeechProvider):
    """Voz neuronal local con Piper (requiere modelo descargado)."""
    name = "piper"
    display_name = "Piper (local, neuronal)"
    default_priority = 10
    default_params = {"model_dir": "", "noise_scale": 0.667, "noise_w_scale": 0.8, "sentence_silence_s": 0.15}

    def __init__(self, params=None, credentials=None):
        super().__init__(params, credentials)
        self._voices: dict[str, object] = {}

    @property
    def model_dir(self) -> Path:
        d = self.params.get("model_dir") or str(REPO_ROOT / "data" / "models" / "piper")
        return Path(d)

    def _models(self) -> dict[str, Path]:
        if not self.model_dir.exists():
            return {}
        return {p.name.removesuffix(".onnx"): p for p in sorted(self.model_dir.rglob("*.onnx"))
                if p.with_suffix(".onnx.json").exists()}

    def health_check(self) -> HealthStatus:
        try:
            import piper  # noqa: F401
        except ImportError:
            return HealthStatus(ok=False, message="piper-tts no instalado (pip install piper-tts)")
        if not self._models():
            return HealthStatus(ok=False, message=f"Sin modelos de voz en {self.model_dir}")
        return HealthStatus(ok=True, message=f"{len(self._models())} voces")

    def capabilities(self):
        return {"local": True, "quality": "natural", "speed_control": True}

    def list_voices(self, language: str | None = None) -> list[Voice]:
        voices = []
        for vid, path in self._models().items():
            cfg = json.loads(path.with_suffix(".onnx.json").read_text(encoding="utf-8"))
            lang = (cfg.get("language", {}) or {}).get("code") or vid.split("-")[0]
            if language and not lang.lower().startswith(language.lower()):
                continue
            voices.append(Voice(id=vid, name=vid, language=lang.replace("_", "-")))
        return voices

    def _load(self, vid: str):
        if vid not in self._voices:
            from piper import PiperVoice
            self._voices[vid] = PiperVoice.load(self._models()[vid])
        return self._voices[vid]

    def synthesize(self, request: TTSRequest) -> MediaAsset:
        models = self._models()
        if not models:
            raise ProviderNotConfigured(f"Piper sin modelos en {self.model_dir}")
        vid = request.voice_id if request.voice_id in models else next(
            (v.id for v in self.list_voices(request.language)), None)
        if vid is None:
            raise ProviderError(self.name, f"No hay voz Piper para el idioma {request.language}", transient=False)
        from piper import SynthesisConfig
        voice = self._load(vid)
        cfg = SynthesisConfig(length_scale=1.0 / max(0.5, request.speed), noise_scale=self.params["noise_scale"],
                              noise_w_scale=self.params["noise_w_scale"])
        request.out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with wave.open(str(request.out_path), "wb") as wf:
                voice.synthesize_wav(request.text, wf, syn_config=cfg)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(self.name, f"Piper falló: {e}", transient=False) from e
        with wave.open(str(request.out_path), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(request.out_path), duration_s=round(dur, 3),
                          provider=self.name, prompt=request.text,
                          license=License(name="model-card", attribution=f"Piper voice {vid}"),
                          metadata={"voice": vid})
