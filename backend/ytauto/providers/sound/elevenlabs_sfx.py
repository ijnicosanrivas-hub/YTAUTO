"""Efectos de sonido generados con ElevenLabs (de pago, con la clave de tu cuenta).

API oficial: POST /v1/sound-generation {text, duration_seconds (0,5–30, opcional), prompt_influence, model_id}.
Coste (página de precios de ElevenLabs): 200 créditos por efecto con duración automática o 40 por segundo con
duración fija. Antes de cada efecto se mira el saldo real del plan; si no llega, se usa el efecto local.

Solo se ocupa de los efectos NARRATIVOS descritos en el guion (`descriptive=True`: «pasos acercándose», «puerta que
cruje»…). Los genéricos de montaje (whoosh, impact, riser…) los siguen haciendo los efectos locales gratuitos.
"""
from __future__ import annotations

import hashlib
import subprocess
import wave
from pathlib import Path

import httpx

from ...core.errors import ProviderError, ProviderSkip
from ...core.models import AssetKind, License, MediaAsset
from ..http import client, request
from ..interfaces import CostEstimate, HealthStatus, SFXRequest, SoundEffectsProvider
from ..voice.elevenlabs import BASE, ElevenLabsTTSProvider

CREDITS_AUTO = 200
CREDITS_PER_SECOND = 40


class ElevenLabsSFXProvider(SoundEffectsProvider):
    """Efectos de sonido a medida con IA (ElevenLabs)."""
    name = "elevenlabs_sfx"
    display_name = "ElevenLabs · efectos de sonido (de pago)"
    is_paid = True
    is_local = False
    requires_network = True
    required_credentials = ["api_key"]
    default_priority = 5
    default_params = {"price_per_1k_chars_eur": None, "model_id": "eleven_text_to_sound_v3",
                      "prompt_influence": 0.4, "reserve_credits": 2000, "check_subscription": True,
                      "output_format": "mp3_44100_128"}
    _transport: httpx.BaseTransport | None = None

    def capabilities(self):
        return {"descriptive_only": True, "needs_price_param": True,
                "cost": f"{CREDITS_AUTO} créditos por efecto o {CREDITS_PER_SECOND}/s con duración fija"}

    def _tts(self) -> ElevenLabsTTSProvider:
        t = ElevenLabsTTSProvider(params={"reserve_credits": self.params.get("reserve_credits"),
                                          "check_subscription": self.params.get("check_subscription", True),
                                          "price_per_1k_chars_eur": self.params.get("price_per_1k_chars_eur")},
                                  credentials=self.credentials)
        t._transport = self._transport
        return t

    def health_check(self) -> HealthStatus:
        base = super().health_check()
        if not base.ok:
            return base
        if self.params.get("price_per_1k_chars_eur") in (None, ""):
            return HealthStatus(ok=False, message="Configura el precio de tu plan (price_per_1k_chars_eur)")
        return HealthStatus(ok=True, message="Configurado")

    def credits_for(self, req: SFXRequest) -> int:
        if req.duration_s:
            return int(round(min(30.0, max(0.5, req.duration_s)) * CREDITS_PER_SECOND + 0.499))
        return CREDITS_AUTO

    def estimate_cost(self, operation, request_):
        if not getattr(request_, "descriptive", False):
            return CostEstimate(detail="efecto genérico: lo hace el generador local")
        credits = self.credits_for(request_)
        price = float(self.params.get("price_per_1k_chars_eur") or 0)
        return CostEstimate(amount_eur=round(credits / 1000 * price, 6), units=credits, unit_name="créditos",
                            detail=f"{credits} créditos (tarifa oficial de efectos de sonido)")

    def get_effect(self, req: SFXRequest) -> MediaAsset:
        if not req.descriptive:
            raise ProviderSkip(self.name, "efecto genérico de montaje: se usa el local")
        prompt = req.effect.strip()[:450]
        if not prompt:
            raise ProviderSkip(self.name, "efecto sin descripción")
        credits = self.credits_for(req)
        sub = self._tts()._guard_credits(prompt, need=credits)
        body: dict = {"text": prompt, "prompt_influence": self.params.get("prompt_influence", 0.4),
                      "model_id": self.params.get("model_id") or "eleven_text_to_sound_v3"}
        if req.duration_s:
            body["duration_seconds"] = round(min(30.0, max(0.5, req.duration_s)), 2)
        with client(self._transport) as c:
            r = request(self.name, c, "POST", f"{BASE}/v1/sound-generation", [self.credentials["api_key"]],
                        params={"output_format": self.params.get("output_format", "mp3_44100_128")},
                        headers={"xi-api-key": self.credentials["api_key"]}, json=body)
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:10]
        req.out_dir.mkdir(parents=True, exist_ok=True)
        raw = req.out_dir / f"sfx_ai_{digest}.mp3"
        out = raw.with_suffix(".wav")
        raw.write_bytes(r.content)
        proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-ar", "48000",
                               "-ac", "2", str(out)], capture_output=True, encoding="utf-8", errors="replace")
        raw.unlink(missing_ok=True)
        if proc.returncode != 0:
            raise ProviderError(self.name, f"No se pudo convertir el efecto: {proc.stderr[-200:]}", transient=False)
        with wave.open(str(out), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        price = float(self.params.get("price_per_1k_chars_eur") or 0)
        commercial = sub.get("commercial_use") if sub else None
        return MediaAsset(kind=AssetKind.AUDIO_SFX, path=str(Path(out)), duration_s=round(dur, 3), provider=self.name,
                          prompt=prompt, cost_eur=round(credits / 1000 * price, 6),
                          license=License(name="provider-terms", url="https://elevenlabs.io/terms",
                                          attribution="Efecto generado con ElevenLabs", commercial_use=commercial),
                          metadata={"credits": credits, "model_id": body["model_id"]})
