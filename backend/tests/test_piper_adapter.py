"""Adaptador Piper con una voz simulada que respeta la API real (no hay modelo descargado en CI)."""
from __future__ import annotations

import json
import wave

import pytest

from ytauto.core.errors import ProviderError, ProviderNotConfigured
from ytauto.providers.interfaces import TTSRequest
from ytauto.providers.voice.piper import PiperTTSProvider

piper = pytest.importorskip("piper")


class FakeVoice:
    last_config = None
    fail = False

    def synthesize_wav(self, text, wav_file, syn_config=None, **_):
        FakeVoice.last_config = syn_config
        if FakeVoice.fail:
            raise RuntimeError("modelo corrupto")
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x01" * int(22050 * 0.1 * len(text.split())))


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    d = tmp_path / "models" / "es"
    d.mkdir(parents=True)
    for name, lang in (("es_ES-test-medium", "es_ES"), ("en_US-test-low", "en_US")):
        (d / f"{name}.onnx").write_bytes(b"x")
        (d / f"{name}.onnx.json").write_text(json.dumps({"language": {"code": lang}}))
    monkeypatch.setattr(piper.PiperVoice, "load", staticmethod(lambda path, *a, **k: FakeVoice()))
    FakeVoice.fail = False
    return tmp_path / "models"


def test_health_and_voice_listing_by_language(model_dir):
    p = PiperTTSProvider(params={"model_dir": str(model_dir)})
    assert p.health_check().ok and "2 voces" in p.health_check().message
    assert [v.id for v in p.list_voices("es")] == ["es_ES-test-medium"]
    assert {v.language for v in p.list_voices()} == {"es-ES", "en-US"}


def test_synthesis_speed_maps_to_length_scale_and_returns_real_duration(model_dir, tmp_path):
    p = PiperTTSProvider(params={"model_dir": str(model_dir)})
    a = p.synthesize(TTSRequest(text="una dos tres cuatro", language="es", speed=1.25, out_path=tmp_path / "o.wav"))
    assert FakeVoice.last_config.length_scale == pytest.approx(1 / 1.25)  # más rápido = escala menor
    with wave.open(str(tmp_path / "o.wav")) as w:
        assert a.duration_s == pytest.approx(w.getnframes() / w.getframerate(), abs=0.01)
    assert a.metadata["voice"] == "es_ES-test-medium" and a.kind.value == "audio_voice"
    explicit = p.synthesize(TTSRequest(text="hello", language="en", voice_id="en_US-test-low", out_path=tmp_path / "e.wav"))
    assert explicit.metadata["voice"] == "en_US-test-low"


def test_missing_models_and_unsupported_language_and_engine_failure(model_dir, tmp_path):
    empty = PiperTTSProvider(params={"model_dir": str(tmp_path / "vacio")})
    assert not empty.health_check().ok
    with pytest.raises(ProviderNotConfigured):
        empty.synthesize(TTSRequest(text="hola", out_path=tmp_path / "x.wav"))
    p = PiperTTSProvider(params={"model_dir": str(model_dir)})
    with pytest.raises(ProviderError) as e:
        p.synthesize(TTSRequest(text="bonjour", language="fr", out_path=tmp_path / "f.wav"))
    assert not e.value.transient and "fr" in str(e.value)
    FakeVoice.fail = True
    with pytest.raises(ProviderError) as e:
        p.synthesize(TTSRequest(text="hola", language="es", out_path=tmp_path / "g.wav"))
    assert "Piper falló" in str(e.value)
