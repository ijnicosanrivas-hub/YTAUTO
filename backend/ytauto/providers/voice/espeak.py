"""Voz local con espeak-ng (gratuito, sin red). Calidad robótica: útil como respaldo.

Para una voz más natural sin coste usa el adaptador `piper` con un modelo descargado.
"""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ..interfaces import HealthStatus, TextToSpeechProvider, TTSRequest, Voice

WINDOWS_PATHS = ["C:/Program Files/eSpeak NG/espeak-ng.exe", "C:/Program Files (x86)/eSpeak NG/espeak-ng.exe"]
BASE_WPM = 150  # ≈2,5 palabras/s: la velocidad que asume el guionista


def find_binary(name: str) -> str | None:
    """espeak-ng en el PATH o, en Windows, en la carpeta donde lo instala su instalador (que no siempre lo añade)."""
    found = shutil.which(name)
    if found:
        return found
    return next((p for p in WINDOWS_PATHS if Path(p).exists()), None)


class EspeakTTSProvider(TextToSpeechProvider):
    """Síntesis de voz local con espeak-ng."""
    name = "espeak"
    display_name = "espeak-ng (local)"
    default_priority = 50
    default_params = {"binary": "espeak-ng", "base_wpm": BASE_WPM, "pitch": 45, "variant": ""}

    def health_check(self) -> HealthStatus:
        if not find_binary(self.params["binary"]):
            return HealthStatus(ok=False, message="espeak-ng no instalado (Linux: apt install espeak-ng · "
                                                  "Windows: winget install eSpeak-NG.eSpeak-NG)")
        return HealthStatus(ok=True, message="espeak-ng disponible")

    def capabilities(self):
        return {"local": True, "quality": "básica", "speed_control": True, "languages": ["es", "en", "pt", "fr", "…"]}

    def list_voices(self, language: str | None = None) -> list[Voice]:
        binary = find_binary(self.params["binary"])
        if not binary:
            return []
        cmd = [binary, f"--voices={language}" if language else "--voices"]
        out = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace").stdout.splitlines()[1:]
        voices = []
        for line in out:
            cols = line.split()
            if len(cols) < 5 or cols[4].startswith("mb/"):
                continue  # las voces MBROLA requieren paquetes adicionales
            lang, gender, name = cols[1], cols[2].split("/")[-1], cols[3]
            voices.append(Voice(id=lang, name=name.replace("_", " "), language=lang,
                                gender={"M": "male", "F": "female"}.get(gender)))
        return voices

    def synthesize(self, request: TTSRequest) -> MediaAsset:
        if not request.text.strip():
            raise ProviderError(self.name, "Texto vacío", transient=False)
        request.out_path.parent.mkdir(parents=True, exist_ok=True)
        voice = request.voice_id or request.language
        if self.params.get("variant"):
            voice = f"{voice}+{self.params['variant']}"
        wpm = int(self.params["base_wpm"] * request.speed)
        raw = request.out_path.with_suffix(".raw.wav")
        binary = find_binary(self.params["binary"])
        if not binary:
            raise ProviderError(self.name, "espeak-ng no está instalado", transient=False)
        # El texto va en un fichero UTF-8, no como argumento: en Windows los argumentos con tildes o «¿» se corrompen.
        textfile = request.out_path.with_suffix(".txt")
        textfile.write_text(request.text, encoding="utf-8")
        try:
            proc = subprocess.run([binary, "-v", voice, "-s", str(wpm), "-p", str(self.params["pitch"]),
                                   "-w", str(raw), "-f", str(textfile)], capture_output=True, encoding="utf-8",
                                  errors="replace", timeout=120)
        finally:
            textfile.unlink(missing_ok=True)
        if proc.returncode != 0 or not raw.exists():
            raise ProviderError(self.name, f"espeak-ng falló: {proc.stderr[-300:]}", transient=False)
        # Normaliza a 48 kHz mono y recorta silencios de los extremos.
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                            "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                            "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                            "-ar", "48000", "-ac", "1", str(request.out_path)], check=True)
            raw.unlink(missing_ok=True)
        else:
            raw.replace(request.out_path)
        with wave.open(str(request.out_path), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(request.out_path), duration_s=round(dur, 3),
                          provider=self.name, prompt=request.text,
                          license=License(name="generated", attribution="espeak-ng (GPLv3, salida libre)",
                                          commercial_use=True),
                          metadata={"voice": voice, "wpm": wpm})


def _which(binary: str) -> str | None:
    return shutil.which(binary) or (binary if Path(binary).exists() else None)
