"""Agente de audio con ElevenLabs avanzado: interpretación (v4), diálogos, efectos IA, tiempos por palabra,
Voice Changer, diseño de voces y cuestionario de capacidades. Siempre contra un ElevenLabs SIMULADO."""
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_agents import PIPE, run_until
from ytauto.core import audio_features as af
from ytauto.core.errors import ProviderSkip
from ytauto.core.models import AssetKind, MediaAsset, Script
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM
from ytauto.providers.interfaces import DialogueLine, SFXRequest, TTSRequest
from ytauto.providers.interfaces import ProviderCategory as C
from ytauto.providers.sound.elevenlabs_sfx import ElevenLabsSFXProvider
from ytauto.providers.voice.elevenlabs import ElevenLabsTTSProvider

KEY = "sk_test_AUDIO_0123456789"


@pytest.fixture(scope="module")
def mp3(tmp_path_factory):
    out = tmp_path_factory.mktemp("a") / "t.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=330:d=2", str(out)], check=True)
    return out.read_bytes()


def alignment_for(text: str, step: float = 0.05) -> dict:
    return {"characters": list(text), "character_start_times_seconds": [i * step for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(text))]}


def eleven_server(mp3: bytes, sub: dict | None = None):
    seen: list[httpx.Request] = []
    sub = sub or {"tier": "creator", "character_count": 1000, "character_limit": 121000}

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        p = r.url.path
        if p == "/v1/user/subscription":
            return httpx.Response(200, json=sub)
        if p == "/v1/voices":
            return httpx.Response(200, json={"voices": [{"voice_id": "NARR", "name": "Narrador"}]})
        if p.endswith("/with-timestamps"):
            body = json.loads(r.content)
            text = "".join(i["text"] for i in body["inputs"]) if "inputs" in body else body["text"]
            return httpx.Response(200, json={"audio_base64": base64.b64encode(mp3).decode(),
                                             "alignment": alignment_for(text), "voice_segments": []})
        if p.startswith(("/v1/voice-changer/", "/v1/text-to-speech/", "/v1/sound-generation")):
            return httpx.Response(200, content=mp3)
        if p == "/v1/text-to-voice/design":
            return httpx.Response(200, json={"text": "muestra", "previews": [
                {"generated_voice_id": f"G{i}", "audio_base_64": base64.b64encode(b"x").decode(), "media_type": "audio/mpeg"}
                for i in range(3)]})
        if p == "/v1/text-to-voice":
            return httpx.Response(200, json={"voice_id": "NEWVOICE", "name": json.loads(r.content)["voice_name"]})
        return httpx.Response(404)
    return httpx.MockTransport(handler), seen


def tts(mp3, **params):
    t, seen = eleven_server(mp3)
    p = ElevenLabsTTSProvider(params={"price_per_1k_chars_eur": 0.165, **params}, credentials={"api_key": KEY})
    p._transport = t
    return p, seen


# ------------------------------------------------------------------ utilidades de etiquetas y tiempos
def test_tags_timings_and_dialogue_parsing():
    assert af.strip_tags("[whispers] Nadie lo vio venir… [sighs] Nadie.") == "Nadie lo vio venir… Nadie."
    assert af.same_words("Nadie lo vio venir.", "[whispers] Nadie lo vio... VENIR.")
    assert not af.same_words("Nadie lo vio venir.", "[whispers] Nadie lo vio llegar.")
    text = "[whispers] Hola mundo"
    words = af.words_from_alignment(alignment_for(text), offset_s=1.0)
    assert [w["word"] for w in words] == ["Hola", "mundo"] and words[0]["start_s"] == pytest.approx(1.55)
    mapped = af.map_to_plain("hola, mundo", [{"word": "HOLA", "start_s": 0, "end_s": 1}, {"word": "mundo…", "start_s": 1, "end_s": 2}])
    assert [m["word"] for m in mapped] == ["hola,", "mundo"]
    assert af.map_to_plain("otra cosa", words) is None
    assert af.parse_dialogue(["Testigo: Yo no vi nada", "sin papel", "Policía: ¿Seguro?"]) == [
        ("testigo", "Yo no vi nada"), ("policía", "¿Seguro?")]
    assert af.role_voice("policía", {"secundario": "S", "narrador": "N"}) == "S"
    assert af.tier_allows("creator", "creator") and af.tier_allows("starter", "creator") is False
    assert af.tier_allows(None, "free") is None


def test_feature_questionnaire_reflects_the_plan():
    view = {f["id"]: f for f in af.feature_view(["expressive"], "starter")}
    assert view["expressive"]["enabled"] and not view["sfx"]["enabled"]
    assert view["pro_clone"]["plan_ok"] is False and view["voice_changer"]["plan_ok"] is True
    assert view["studio"]["in_app"] is False  # Studio/Actor Mode: solo en la web de ElevenLabs (se explica)
    assert "200 créditos" in view["sfx"]["cost"] and "1.000 créditos" in view["voice_changer"]["cost"]


# ------------------------------------------------------------------ adaptador de voz
def test_emotional_performance_goes_through_eleven_v4_dialogue_with_word_timings(tmp_path, mp3):
    p, seen = tts(mp3)
    a = p.synthesize(TTSRequest(text="Nadie lo vio venir.", voice_id="NARR", out_path=tmp_path / "a.wav",
                                performance_text="[whispers] Nadie lo vio... VENIR.", want_word_timings=True))
    r = seen[-1]
    body = json.loads(r.content)
    assert r.url.path == "/v1/text-to-dialogue/with-timestamps" and body["model_id"] == "eleven_v4"
    assert body["inputs"] == [{"text": "[whispers] Nadie lo vio... VENIR.", "voice_id": "NARR"}]
    assert [w["word"] for w in a.metadata["word_timings"]] == ["Nadie", "lo", "vio", "venir."]  # palabras del guion
    assert a.metadata["mode"] == "dialogue" and a.metadata["credits"] == len("[whispers] Nadie lo vio... VENIR.")


def test_multi_voice_dialogue_and_plain_timestamps(tmp_path, mp3):
    p, seen = tts(mp3)
    lines = [DialogueLine(voice_id="NARR", text="Aquella noche…"), DialogueLine(voice_id="WIT", text="Yo no vi nada.")]
    a = p.synthesize(TTSRequest(text="Aquella noche… Yo no vi nada.", out_path=tmp_path / "d.wav", dialogue=lines))
    body = json.loads(seen[-1].content)
    assert [i["voice_id"] for i in body["inputs"]] == ["NARR", "WIT"] and a.metadata["voices"] == ["NARR", "WIT"]
    b = p.synthesize(TTSRequest(text="Hola canal", voice_id="NARR", out_path=tmp_path / "b.wav", want_word_timings=True))
    assert seen[-1].url.path == "/v1/text-to-speech/NARR/with-timestamps" and len(b.metadata["word_timings"]) == 2
    with pytest.raises(Exception) as e:
        p.synthesize(TTSRequest(text="x", out_path=tmp_path / "c.wav", dialogue=[DialogueLine(voice_id="N", text="x" * 2100)]))
    assert "2000" in str(e.value)


def test_voice_changer_charges_by_minute_and_keeps_the_brake(tmp_path, mp3):
    ref = tmp_path / "mi_toma.mp3"
    ref.write_bytes(mp3)  # 2 s
    p, seen = tts(mp3)
    a = p.synthesize(TTSRequest(text="Frase grabada", voice_id="NARR", out_path=tmp_path / "v.wav", reference_audio=ref))
    r = seen[-1]
    assert r.url.path == "/v1/voice-changer/NARR" and b"eleven_multilingual_sts_v2" in r.content
    assert a.metadata["credits"] == 34  # 2 s de 1.000 créditos/minuto, redondeado hacia arriba


def test_voice_design_creates_a_voice_from_a_description(mp3):
    p, seen = tts(mp3)
    d = p.design_voice("Narrador grave de documental, misterioso, ritmo pausado")
    assert len(d["previews"]) == 3 and json.loads(seen[-1].content)["auto_generate_text"] is True
    v = p.create_voice("G1", "Narrador Gotham", "grave")
    assert v["voice_id"] == "NEWVOICE" and json.loads(seen[-1].content)["generated_voice_id"] == "G1"


# ------------------------------------------------------------------ efectos con IA
def test_ai_sfx_only_for_narrative_effects_with_official_costs(tmp_path, mp3):
    t, seen = eleven_server(mp3)
    p = ElevenLabsSFXProvider(params={"price_per_1k_chars_eur": 0.165}, credentials={"api_key": KEY})
    p._transport = t
    with pytest.raises(ProviderSkip):
        p.get_effect(SFXRequest(effect="whoosh", out_dir=tmp_path))
    assert p.estimate_cost("get_effect", SFXRequest(effect="whoosh", out_dir=tmp_path)).amount_eur == 0
    a = p.get_effect(SFXRequest(effect="slow footsteps approaching on a wooden floor", out_dir=tmp_path, descriptive=True))
    body = json.loads(seen[-1].content)
    assert seen[-1].url.path == "/v1/sound-generation" and body["model_id"] == "eleven_text_to_sound_v3"
    assert a.metadata["credits"] == 200 and a.kind is AssetKind.AUDIO_SFX and Path(a.path).exists()
    assert p.credits_for(SFXRequest(effect="x y", duration_s=3, out_dir=tmp_path)) == 120  # 40 por segundo


def test_generic_effects_skip_the_paid_generator_silently(tmp_path):
    from cryptography.fernet import Fernet
    from ytauto.db.schema import make_engine
    from ytauto.providers.registry import (
        BudgetManager,
        CredentialVault,
        ProviderRegistry,
        RegistryGateway,
    )
    engine = make_engine(tmp_path / "s.db")
    reg = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()))
    reg.seed_defaults()
    reg.add("elevenlabs_sfx", params={"price_per_1k_chars_eur": 0.1, "check_subscription": False},
            credentials={"api_key": KEY})
    reg.set_primary(C.SFX, "elevenlabs_sfx")
    gw = RegistryGateway(reg, BudgetManager(engine, project_budget=lambda pid: 5.0), is_spend_authorized=lambda *a: True)
    asset = gw.invoke(C.SFX, "get_effect", SFXRequest(effect="whoosh", out_dir=tmp_path), project_id="p")
    assert asset.provider != "elevenlabs_sfx" and reg.status("elevenlabs_sfx").error_count == 0


# ------------------------------------------------------------------ agente de voz completo
class FakeTTS:
    """Proveedor de voz que registra lo que le piden y devuelve tiempos por palabra como ElevenLabs."""

    def __init__(self):
        self.requests: list[TTSRequest] = []

    def __call__(self, req: TTSRequest) -> MediaAsset:
        self.requests.append(req)
        from ytauto.providers.audio_synth import synth_music, write_wav
        write_wav(req.out_path, synth_music("calm", 2.0))
        words = req.text.split()
        timings = [{"word": w, "start_s": i * 0.3, "end_s": i * 0.3 + 0.25} for i, w in enumerate(words)]
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(req.out_path), duration_s=2.0, provider="fake",
                          metadata={"word_timings": timings} if req.want_word_timings else {})


def test_voice_agent_performs_casts_dialogue_and_uses_exact_word_timings(make_ctx, mock_providers, spec):
    fake = FakeTTS()
    mock_providers[C.TTS].synthesize = fake
    performed = {}

    def voice_llm(req):
        out = {int(k): f"[whispers] {v}" for k, v in req.context["scenes"].items()}
        performed.update(out)
        return {"scenes": out}
    spec2 = spec.model_copy(update={"audio_features": ["expressive", "dialogue", "word_timing"],
                                    "voice_cast": {"narrador": "NARR", "secundario": "WIT"}})
    ctx = make_ctx(llm=ScriptedLLM({"voice": voice_llm, "director": lambda r: LocalDraftLLM()._director(r.context),
                                    "scriptwriter": lambda r: LocalDraftLLM()._scriptwriter(r.context),
                                    "resources": lambda r: LocalDraftLLM()._resources(r.context)}),
                   spec_override=spec2)
    run_until(ctx, *PIPE[:3])
    script = ctx.workspace.load("scripts", "script", Script)
    script.scenes[1].dialogue = ["Testigo: Yo no vi nada"]
    ctx.workspace.save("scripts", "script", script)
    run_until(ctx, "voice")
    assert performed and all(r.want_word_timings for r in fake.requests)
    with_dialogue = [r for r in fake.requests if r.dialogue]
    assert len(with_dialogue) == 1 and [d.voice_id for d in with_dialogue[0].dialogue] == ["NARR", "WIT"]
    assert with_dialogue[0].dialogue[0].text.startswith("[whispers]")  # el narrador también interpreta
    assert "Yo no vi nada" in with_dialogue[0].text  # el diálogo suena y sale en subtítulos
    solo = [r for r in fake.requests if not r.dialogue]
    assert all(r.performance_text and r.performance_text.startswith("[whispers]") for r in solo)
    manifest = ctx.workspace.load("voice", "voice_manifest")
    cues = manifest["cues"]
    assert cues and all(c["words"] for c in cues)  # subtítulos palabra a palabra
    assert not any("[" in c["text"] for c in cues)  # sin etiquetas en pantalla


def test_without_features_nothing_changes(make_ctx, mock_providers):
    fake = FakeTTS()
    mock_providers[C.TTS].synthesize = fake
    ctx = make_ctx()
    run_until(ctx, *PIPE[:3], "voice")
    assert fake.requests and not any(r.performance_text or r.dialogue or r.want_word_timings for r in fake.requests)


# ------------------------------------------------------------------ cuestionario, reparto y Voice Changer por API
@pytest.fixture
def client(tmp_path, monkeypatch, mp3):
    from ytauto.api.server import create_api
    from ytauto.app import build_app
    from ytauto.core.settings import Settings
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    monkeypatch.delenv("YTAUTO_API_TOKEN", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    t, _ = eleven_server(mp3)
    monkeypatch.setattr(ElevenLabsTTSProvider, "_transport", t)
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)
    return app, TestClient(create_api(app))


def test_questionnaire_cast_design_and_reference_upload(client, mp3):
    app, c = client
    v = c.get("/api/accounts").json()["elevenlabs"]
    assert v["features_answered"] is False and {f["id"] for f in v["features"]} >= {"expressive", "sfx", "dialogue"}
    # Se puede contestar antes de vincular la cuenta: se aplica al vincularla.
    early = c.put("/api/accounts/elevenlabs/features", json={"features": ["sfx"]}).json()
    assert early["features_answered"] and early["sfx"]["linked"] is False
    c.post("/api/accounts/elevenlabs", json={"api_key": KEY, "plan_price_eur": 20, "plan_credits": 121000})
    assert c.get("/api/accounts").json()["elevenlabs"]["sfx"]["linked"] is True
    r = c.put("/api/accounts/elevenlabs/features", json={"features": ["expressive", "sfx", "dialogue", "pro_clone"]}).json()
    on = {f["id"] for f in r["features"] if f["enabled"]}
    assert on == {"expressive", "sfx", "dialogue"} and r["features_answered"] and r["sfx"]["linked"]
    reg = app.provider_system.registry
    assert reg.vault.get_all("elevenlabs_sfx")["api_key"] == KEY and reg.get("elevenlabs_sfx").max_generations_per_project == 6
    assert c.put("/api/accounts/elevenlabs/features", json={"features": ["expressive"]}).json()["sfx"]["linked"] is False
    assert c.put("/api/accounts/elevenlabs/cast", json={"channel": "general", "role": "narrador", "voice_id": "NARR"}).status_code == 200
    assert c.put("/api/accounts/elevenlabs/cast", json={"channel": "general", "role": "villano", "voice_id": "X"}).status_code == 400
    d = c.post("/api/accounts/elevenlabs/voice-design", json={"description": "Narrador grave y misterioso de documental"}).json()
    assert len(d["previews"]) == 3
    s = c.post("/api/accounts/elevenlabs/voice-design/save", json={"generated_voice_id": "G0", "name": "Villano",
                                                                   "description": "grave", "channel": "general",
                                                                   "role": "antagonista"}).json()
    assert "cast" in s, s
    assert s["cast"]["general"] == {"narrador": "NARR", "antagonista": "NEWVOICE"}
    proj = c.post("/api/projects", json={"name": "A", "topic": "t", "duration_s": 45, "audio_features": ["expressive"],
                                         "require_script_approval": True}).json()
    pid = proj["project"]["id"]
    assert proj["project"]["spec"]["voice_cast"] == {"narrador": "NARR", "antagonista": "NEWVOICE"}
    assert c.post("/api/projects", json={"name": "B", "topic": "t", "duration_s": 45,
                                         "audio_features": ["inventada"]}).status_code == 400
    up = c.post(f"/api/projects/{pid}/voice-reference/2", json={"filename": "toma.mp3",
                                                                "data_b64": base64.b64encode(mp3).decode()})
    assert up.status_code == 201 and c.get(f"/api/projects/{pid}/voice-reference").json()["scenes"] == [2]
    assert c.delete(f"/api/projects/{pid}/voice-reference/2").json()["ok"]
    assert c.get(f"/api/projects/{pid}/voice-reference").json()["scenes"] == []
