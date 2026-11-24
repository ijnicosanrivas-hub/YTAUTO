"""Voz del sistema en macOS (`say`): SOLO PARA PRUEBAS INTERNAS. No se da de alta sola.

La licencia de macOS permite usar sus voces del sistema únicamente para contenido personal y NO comercial, y excluye
publicarlas o distribuirlas. Por eso este adaptador no se registra automáticamente, marca su audio como no comercial
y la voz por defecto en Mac es eSpeak NG (instalada con Homebrew por INSTALAR_MAC.command).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import wave

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ..interfaces import HealthStatus, TextToSpeechProvider, TTSRequest, Voice

_LINE = re.compile(r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2,3}[_-][A-Za-z0-9]+)\s+#")
# Voces preferidas por idioma (las más naturales que trae macOS); si no están, la primera del idioma.
PREFERRED = {"es": ["Mónica", "Monica", "Jorge", "Paulina", "Juan"], "en": ["Samantha", "Alex", "Daniel"],
             "pt": ["Luciana", "Joana"], "fr": ["Thomas", "Amélie", "Amelie"]}


def parse_voices(text: str) -> list[tuple[str, str]]:
    """Salida de `say -v ?` → [(nombre, locale)]. Los nombres pueden tener espacios y paréntesis."""
    out = []
    for line in text.splitlines():
        m = _LINE.match(line.strip())
        if m:
            out.append((m.group("name").strip(), m.group("locale").replace("-", "_")))
    return out


def choose_voice(voices: list[tuple[str, str]], language: str, wanted: str | None = None) -> str | None:
    """La voz pedida si existe; si no, la preferida del idioma; si no, la primera de ese idioma."""
    names = {n for n, _ in voices}
    if wanted and wanted in names:
        return wanted
    lang = language.split("-")[0].split("_")[0].lower()
    of_lang = [n for n, loc in voices if loc.lower().startswith(lang + "_")]
    for pref in PREFERRED.get(lang, []):
        if pref in of_lang:
            return pref
    return of_lang[0] if of_lang else None


class MacSayTTSProvider(TextToSpeechProvider):
    """Síntesis con las voces del sistema de macOS."""
    name = "macos_say"
    display_name = "Voz del sistema (macOS)"
    default_priority = 90  # detrás de Piper (10) y eSpeak (50)
    auto_register = False  # licencia de Apple: uso personal no comercial; se activa a mano desde Proveedores
    default_params = {"voice": "", "base_wpm": 165}

    def _available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("say") is not None

    def health_check(self) -> HealthStatus:
        if not self._available():
            return HealthStatus(ok=False, message="Solo disponible en macOS")
        return HealthStatus(ok=True, message="Voces del sistema de macOS disponibles")

    def capabilities(self):
        return {"local": True, "quality": "buena", "speed_control": True, "languages": ["es", "en", "pt", "fr", "…"]}

    def _voices(self) -> list[tuple[str, str]]:
        if not self._available():
            return []
        proc = subprocess.run(["say", "-v", "?"], capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        return parse_voices(proc.stdout)

    def list_voices(self, language: str | None = None) -> list[Voice]:
        return [Voice(id=n, name=n, language=loc) for n, loc in self._voices()
                if not language or loc.lower().startswith(language.lower())]

    def synthesize(self, request: TTSRequest) -> MediaAsset:
        if not request.text.strip():
            raise ProviderError(self.name, "Texto vacío", transient=False)
        if not self._available():
            raise ProviderError(self.name, "La voz del sistema solo existe en macOS", transient=False)
        voice = choose_voice(self._voices(), request.language, request.voice_id or self.params.get("voice") or None)
        if not voice:
            raise ProviderError(self.name, f"macOS no tiene ninguna voz para «{request.language}». Añádela en Ajustes del "
                                           "Sistema → Accesibilidad → Contenido leído → Voz del sistema → Gestionar voces",
                                transient=False)
        request.out_path.parent.mkdir(parents=True, exist_ok=True)
        raw = request.out_path.with_suffix(".raw.wav")
        wpm = int(self.params["base_wpm"] * request.speed)
        # El texto entra por la entrada estándar (UTF-8): sin problemas con tildes ni comillas.
        cmd = ["say", "-v", voice, "-r", str(wpm), "--file-format=WAVE", "--data-format=LEI16@24000", "-o", str(raw)]
        try:
            proc = subprocess.run(cmd, input=request.text.encode("utf-8"), capture_output=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ProviderError(self.name, f"La voz del sistema no respondió: {e}", transient=False) from e
        if proc.returncode != 0 or not raw.exists():
            detail = (proc.stderr or b"").decode("utf-8", "replace").strip() or "sin mensaje de error"
            raise ProviderError(self.name, f"say falló (código {proc.returncode}, voz «{voice}»): {detail[-300:]}", transient=False)
        if shutil.which("ffmpeg"):  # 48 kHz mono y sin silencios en los extremos, como el resto de voces
            norm = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                                   "-ar", "48000", "-ac", "1", str(request.out_path)], capture_output=True)
            if norm.returncode != 0:
                raise ProviderError(self.name, "FFmpeg no pudo preparar la voz: "
                                               f"{norm.stderr.decode('utf-8', 'replace')[-300:]}", transient=False)
            raw.unlink(missing_ok=True)
        else:
            raw.replace(request.out_path)
        with wave.open(str(request.out_path), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(request.out_path), duration_s=round(dur, 3),
                          provider=self.name, prompt=request.text,
                          license=License(name="Apple macOS SLA (voces del sistema)", attribution="Voz del sistema de macOS",
                                          commercial_use=False),
                          metadata={"voice": voice, "wpm": wpm})
