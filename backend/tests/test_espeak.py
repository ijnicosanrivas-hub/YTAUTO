"""Voz local eSpeak: copia extraída del MSI (sin registro), rutas con tildes y WAV por la salida estándar."""
from __future__ import annotations

import io
import struct
import subprocess
import wave

import pytest

from ytauto.core.errors import ProviderError
from ytauto.providers.interfaces import TTSRequest
from ytauto.providers.voice import espeak


def _streamed_wav(frames: int = 2205) -> bytes:
    """WAV como lo escribe eSpeak con --stdout: tamaños de relleno porque no puede volver atrás."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x01\x00" * frames)
    data = bytearray(buf.getvalue())
    struct.pack_into("<I", data, 4, 0x7FFFF024)
    struct.pack_into("<I", data, 40, 0x7FFFF000)
    return bytes(data)


def test_fix_wav_header_restores_real_sizes():
    fixed = espeak.fix_wav_header(_streamed_wav(2205))
    with wave.open(io.BytesIO(fixed)) as w:
        assert w.getnframes() == 2205
    assert espeak.fix_wav_header(b"no es un wav") == b"no es un wav"


def test_finds_voice_data_next_to_msi_extracted_exe(tmp_path):
    folder = tmp_path / "tools" / "espeak-ng" / "PFiles" / "eSpeak NG"
    (folder / "espeak-ng-data").mkdir(parents=True)
    exe = folder / "espeak-ng.exe"
    exe.write_bytes(b"")
    assert espeak.find_data_parent(str(exe)) == folder
    assert espeak.find_data_parent(str(tmp_path / "otro" / "espeak-ng.exe")) is None


def _fake(monkeypatch, tmp_path, result):
    folder = tmp_path / "Iñigo" / "eSpeak NG"
    (folder / "espeak-ng-data").mkdir(parents=True)
    exe = folder / "espeak-ng.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(espeak, "find_binary", lambda name: str(exe))
    monkeypatch.setattr(espeak.shutil, "which", lambda name: None)  # sin FFmpeg: se usa el WAV tal cual
    seen = {}

    def run(cmd, **kw):
        seen["cmd"], seen["input"], seen["env"] = cmd, kw.get("input"), kw.get("env")
        return result

    monkeypatch.setattr(espeak.subprocess, "run", run)
    return folder, seen


def test_synthesis_uses_stdin_stdout_and_data_path(monkeypatch, tmp_path):
    ok = subprocess.CompletedProcess([], 0, _streamed_wav(4410), b"")
    folder, seen = _fake(monkeypatch, tmp_path, ok)
    out = tmp_path / "Ñandú con espacios" / "voz.wav"
    asset = espeak.EspeakTTSProvider().synthesize(TTSRequest(text="¿Qué tal, Ñandú?", out_path=out))
    assert f"--path={folder}" in seen["cmd"] and "--stdin" in seen["cmd"] and "--stdout" in seen["cmd"]
    assert seen["input"] == "¿Qué tal, Ñandú?".encode("utf-8")  # el texto nunca va como argumento
    assert seen["env"]["ESPEAK_DATA_PATH"] == str(folder)
    assert asset.duration_s == pytest.approx(0.2, abs=0.01) and out.exists()


def test_failure_message_explains_the_cause(monkeypatch, tmp_path):
    bad = subprocess.CompletedProcess([], 1, b"", b"Error processing file 'phontab'")
    _fake(monkeypatch, tmp_path, bad)
    with pytest.raises(ProviderError) as e:
        espeak.EspeakTTSProvider().synthesize(TTSRequest(text="hola", out_path=tmp_path / "v.wav"))
    assert "código 1" in str(e.value) and "phontab" in str(e.value) and "espeak-ng.exe" in str(e.value)
