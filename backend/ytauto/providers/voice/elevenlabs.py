"""Voz de pago con ElevenLabs (ejemplo de adaptador comercial).

API (documentación oficial): POST /v1/text-to-speech/{voice_id}?output_format=… con cabecera `xi-api-key` y
cuerpo {text, model_id}; devuelve el audio. Voces: GET /v1/voices.

COSTE: no se ha encontrado en la documentación una tarifa fija por carácter, y cambia según el plan, así que el
precio NO tiene valor por defecto: debes indicar `price_per_1k_chars_eur` (de tu plan). Sin él, el adaptador se
declara no disponible y nunca se usa: el control de presupuesto no puede quedar ciego.

El control de velocidad no se usa (el adaptador no lo envía): el agente de voz pedirá recortar el guion si una
locución no cabe en su escena.

SUSCRIPCIÓN (planes Starter/Creator/Pro…): GET /v1/user/subscription devuelve `character_count` (créditos gastados
este ciclo), `character_limit` (créditos del plan), `next_character_count_reset_unix` y `tier`. Antes de cada
locución se comprueba que quedan créditos suficientes (más una reserva): si no, el adaptador se niega y la voz
pasa a la alternativa gratuita (eSpeak/Piper). Así nunca se entra en el uso por encima del plan, que se cobra aparte.
Si la comprobación no puede hacerse, tampoco se sintetiza (falla cerrado: no se gasta a ciegas).

LICENCIA: el plan gratuito no permite uso comercial; los de pago sí. `commercial_use` se toma del `tier` real.
"""
from __future__ import annotations

import subprocess
import time
import wave
from pathlib import Path

import httpx

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ..http import client, request
from ..interfaces import CostEstimate, HealthStatus, TextToSpeechProvider, TTSRequest, Voice

BASE = "https://api.elevenlabs.io"
# Créditos por carácter según el modelo (precios de ElevenLabs: los modelos Flash/Turbo gastan la mitad).
CREDITS_PER_CHAR = {"eleven_flash_v2_5": 0.5, "eleven_flash_v2": 0.5, "eleven_turbo_v2_5": 0.5, "eleven_turbo_v2": 0.5}
FREE_TIERS = {"free"}


def summarize_subscription(data: dict) -> dict:
    """Resumen legible de /v1/user/subscription (función pura, se prueba sin red)."""
    used = int(data.get("character_count") or 0)
    limit = int(data.get("character_limit") or 0)
    tier = str(data.get("tier") or "")
    reset = data.get("next_character_count_reset_unix")
    return {"tier": tier, "used": used, "limit": limit, "remaining": max(0, limit - used),
            "pct": round(used / limit * 100, 1) if limit else 0.0, "resets_at_unix": reset,
            "status": data.get("status"), "commercial_use": tier.lower() not in FREE_TIERS if tier else None,
            "can_extend": bool(data.get("can_extend_character_limit"))}


class ElevenLabsTTSProvider(TextToSpeechProvider):
    """Síntesis de voz con la API de ElevenLabs (de pago)."""
    name = "elevenlabs"
    display_name = "ElevenLabs (voz, de pago)"
    is_paid = True
    is_local = False
    requires_network = True
    required_credentials = ["api_key"]
    default_params = {"model_id": "eleven_multilingual_v2", "output_format": "mp3_44100_128",
                      "price_per_1k_chars_eur": None, "default_voice_id": "",
                      # Créditos que se dejan sin tocar (margen para no rozar el límite del plan).
                      "reserve_credits": 2000, "check_subscription": True}
    _transport: httpx.BaseTransport | None = None
    _sub_cache: tuple[float, dict] | None = None

    def capabilities(self):
        return {"speed_control": False, "quality": "neuronal comercial", "needs_price_param": True}

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.credentials["api_key"]}

    def health_check(self) -> HealthStatus:
        base = super().health_check()
        if not base.ok:
            return base
        if self.params.get("price_per_1k_chars_eur") in (None, ""):
            return HealthStatus(ok=False, message="Configura price_per_1k_chars_eur (precio de tu plan): sin él no "
                                                  "se puede estimar el coste ni aplicar el presupuesto")
        return HealthStatus(ok=True, message="Configurado")

    def verify_connection(self) -> HealthStatus:
        local = self.health_check()
        if not local.ok:
            return local
        try:
            with client(self._transport) as c:
                r = request(self.name, c, "GET", f"{BASE}/v1/voices", [self.credentials["api_key"]],
                            headers=self._headers())
            return HealthStatus(ok=True, message=f"{len(r.json().get('voices', []))} voces disponibles")
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))

    def estimate_cost(self, operation, request_):
        chars = len(getattr(request_, "text", "") or "")
        price = float(self.params.get("price_per_1k_chars_eur") or 0)
        return CostEstimate(amount_eur=round(chars / 1000 * price, 6), units=chars, unit_name="caracteres",
                            detail=f"{price} €/1000 caracteres (precio configurado por el usuario)")

    def credits_for(self, text: str) -> int:
        rate = CREDITS_PER_CHAR.get(str(self.params.get("model_id")), 1.0)
        return int(round(len(text) * rate + 0.499))

    def subscription(self, max_age_s: float = 0.0) -> dict:
        """Créditos reales del plan (lectura, sin coste)."""
        if max_age_s and self._sub_cache and time.time() - self._sub_cache[0] < max_age_s:
            return self._sub_cache[1]
        with client(self._transport) as c:
            r = request(self.name, c, "GET", f"{BASE}/v1/user/subscription", [self.credentials["api_key"]],
                        headers=self._headers())
        info = summarize_subscription(r.json())
        self._sub_cache = (time.time(), info)
        return info

    def _guard_credits(self, text: str) -> dict | None:
        if not self.params.get("check_subscription", True):
            return None
        try:
            sub = self.subscription()
        except ProviderError as e:
            raise ProviderError(self.name, f"no se pudo comprobar el saldo de créditos ({e}); no se gasta a ciegas",
                                transient=e.transient, retry_after_s=e.retry_after_s) from e
        need = self.credits_for(text)
        reserve = int(self.params.get("reserve_credits") or 0)
        if sub["limit"] and sub["remaining"] - need < reserve:
            raise ProviderError(self.name, f"créditos del plan casi agotados: quedan {sub['remaining']}, esta locución "
                                           f"gasta ≈{need} y la reserva es {reserve}. Se usa la voz gratuita.",
                                transient=False)
        return sub

    def list_voices(self, language: str | None = None) -> list[Voice]:
        with client(self._transport) as c:
            r = request(self.name, c, "GET", f"{BASE}/v1/voices", [self.credentials["api_key"]],
                        headers=self._headers())
        voices = []
        for v in r.json().get("voices", []):
            labels = v.get("labels") or {}
            # Los modelos multilingües hablan cualquier idioma con cualquier voz.
            voices.append(Voice(id=v["voice_id"], name=v.get("name", v["voice_id"]), language=language or "multi",
                                gender=labels.get("gender"), style=labels.get("descriptive") or labels.get("use_case")))
        return voices

    def synthesize(self, req: TTSRequest) -> MediaAsset:
        voice_id = req.voice_id or self.params.get("default_voice_id")
        if not voice_id:
            raise ProviderError(self.name, "No hay voz seleccionada (voice_id)", transient=False)
        if not req.text.strip():
            raise ProviderError(self.name, "Texto vacío", transient=False)
        sub = self._guard_credits(req.text)
        with client(self._transport) as c:
            r = request(self.name, c, "POST", f"{BASE}/v1/text-to-speech/{voice_id}", [self.credentials["api_key"]],
                        params={"output_format": self.params["output_format"]}, headers=self._headers(),
                        json={"text": req.text, "model_id": self.params["model_id"]})
        req.out_path.parent.mkdir(parents=True, exist_ok=True)
        raw = req.out_path.with_suffix(".mp3")
        raw.write_bytes(r.content)
        # El resto del sistema trabaja con WAV a 48 kHz mono.
        proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-ar", "48000",
                               "-ac", "1", str(req.out_path)], capture_output=True, encoding="utf-8", errors="replace")
        raw.unlink(missing_ok=True)
        if proc.returncode != 0:
            raise ProviderError(self.name, f"No se pudo convertir el audio recibido: {proc.stderr[-200:]}",
                                transient=False)
        with wave.open(str(req.out_path), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        cost = self.estimate_cost("synthesize", req).amount_eur
        commercial = sub.get("commercial_use") if sub else None
        meta = {"voice": voice_id, "model_id": self.params["model_id"], "credits": self.credits_for(req.text)}
        if sub:
            meta["plan"] = sub["tier"]
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(Path(req.out_path)), duration_s=round(dur, 3),
                          provider=self.name, prompt=req.text, cost_eur=cost,
                          license=License(name="provider-terms", url="https://elevenlabs.io/terms",
                                          attribution="Audio generado con ElevenLabs" if commercial is not False
                                          else "Audio generado con ElevenLabs (plan gratuito: elevenlabs.io)",
                                          commercial_use=commercial),
                          metadata=meta)
