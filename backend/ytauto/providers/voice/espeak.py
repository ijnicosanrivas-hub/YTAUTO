"""Voz local con espeak-ng (gratuito, sin red). Calidad robótica: útil como respaldo.

Para una voz más natural sin coste usa el adaptador `piper` con un modelo descargado.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
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
    from ...core.tools import find_espeak_dir  # instalada por INSTALAR_WINDOWS.bat dentro de tools/
    local = find_espeak_dir()
    if local and (local / "espeak-ng.exe").is_file():
        return str(local / "espeak-ng.exe")
    return next((p for p in WINDOWS_PATHS if Path(p).exists()), None)


def find_data_parent(binary: str) -> Path | None:
    """Carpeta que contiene `espeak-ng-data`. Hace falta cuando eSpeak se extrajo del MSI sin instalarlo
    (lo que hace INSTALAR_WINDOWS.bat): entonces no hay clave de registro y el programa no encuentra sus voces."""
    exe = Path(binary)
    for folder in [exe.parent, *list(exe.parents)[1:4]]:
        if (folder / "espeak-ng-data").is_dir():
            return folder
        for sub in folder.glob("*/espeak-ng-data"):
            if sub.is_dir():
                return sub.parent
    return None


def short_path(path: Path | str) -> str:
    """En Windows, la ruta corta 8.3 (sin tildes ni «ñ»): eSpeak abre los ficheros con la API antigua y falla con ellas."""
    p = str(path)
    if sys.platform != "win32":
        return p
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, len(buf))  # type: ignore[attr-defined]
        return buf.value if 0 < n < len(buf) else p
    except (OSError, AttributeError):
        return p


def fix_wav_header(data: bytes) -> bytes:
    """Con `--stdout`, eSpeak no puede volver atrás a escribir los tamaños del WAV y deja valores de relleno."""
    if len(data) < 44 or data[:4] != b"RIFF":
        return data
    out = bytearray(data)
    struct.pack_into("<I", out, 4, len(data) - 8)
    pos = 12
    while pos + 8 <= len(out):  # busca el bloque «data» (normalmente en el byte 36)
        tag, size = bytes(out[pos:pos + 4]), struct.unpack_from("<I", out, pos + 4)[0]
        if tag == b"data":
            struct.pack_into("<I", out, pos + 4, len(out) - pos - 8)
            break
        pos += 8 + size
    return bytes(out)


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
        # Texto por la entrada estándar (UTF-8) y audio por la salida estándar: sin rutas de fichero, así no le
        # afectan las tildes o espacios de la carpeta del usuario en Windows.
        cmd = [binary, "-v", voice, "-s", str(wpm), "-p", str(self.params["pitch"]), "-b", "1", "--stdin", "--stdout"]
        data_parent = find_data_parent(binary)
        env = dict(os.environ)
        if data_parent:
            cmd.insert(1, f"--path={short_path(data_parent)}")
            env["ESPEAK_DATA_PATH"] = short_path(data_parent)
        try:
            proc = subprocess.run(cmd, input=request.text.encode("utf-8"), capture_output=True, timeout=120, env=env)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ProviderError(self.name, f"espeak-ng no se pudo ejecutar ({binary}): {e}", transient=False) from e
        audio = proc.stdout or b""
        if proc.returncode != 0 or len(audio) < 100 or audio[:4] != b"RIFF":
            detail = (proc.stderr or b"").decode("utf-8", "replace").strip() or "sin mensaje de error"
            hint = "" if data_parent else " · no se encuentra la carpeta espeak-ng-data junto al programa"
            raise ProviderError(self.name, f"espeak-ng falló (código {proc.returncode}, voz «{voice}»): {detail[-300:]}"
                                           f"{hint} · programa: {binary}", transient=False)
        raw.write_bytes(fix_wav_header(audio))
        # Normaliza a 48 kHz mono y recorta silencios de los extremos.
        if shutil.which("ffmpeg"):
            norm = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af",
                                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                                   "-ar", "48000", "-ac", "1", str(request.out_path)], capture_output=True)
            if norm.returncode != 0:
                raise ProviderError(self.name, f"FFmpeg no pudo preparar la voz: {norm.stderr.decode('utf-8', 'replace')[-300:]}",
                                    transient=False)
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
