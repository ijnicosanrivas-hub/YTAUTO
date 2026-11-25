"""«Cuentas conectadas»: vincular ElevenLabs y Higgsfield desde la API, con servicios simulados (sin red ni gasto)."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from test_higgsfield import FakeCLI
from ytauto.api import accounts_api
from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.settings import Settings
from ytauto.llm.mock import LocalDraftLLM
from ytauto.providers import higgsfield as hf
from ytauto.providers.video.higgsfield import HiggsfieldVideoProvider
from ytauto.providers.voice.elevenlabs import ElevenLabsTTSProvider

KEY = "sk_test_ELEVEN_0123456789"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    monkeypatch.delenv("YTAUTO_API_TOKEN", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)

    def eleven(r: httpx.Request):
        if r.headers.get("xi-api-key") != KEY:
            return httpx.Response(401, json={"detail": "invalid_api_key"})
        if r.url.path == "/v1/user/subscription":
            return httpx.Response(200, json={"tier": "creator", "character_count": 21000, "character_limit": 121000,
                                             "next_character_count_reset_unix": 1767225600})
        if r.url.path == "/v1/voices":
            return httpx.Response(200, json={"voices": [{"voice_id": "VOZ1", "name": "Lucía"}]})
        return httpx.Response(404)
    monkeypatch.setattr(ElevenLabsTTSProvider, "_transport", httpx.MockTransport(eleven))
    cli = FakeCLI(credits=1200)
    monkeypatch.setattr(HiggsfieldVideoProvider, "_runner", staticmethod(cli))
    fake_bin = tmp_path / "hf"
    fake_bin.write_text("#")
    monkeypatch.setattr(hf, "find_cli", lambda explicit="", **kw: str(fake_bin))
    return app, TestClient(create_api(app)), cli


def test_link_elevenlabs_with_key_plan_and_live_credits(env):
    app, c, _ = env
    assert c.get("/api/accounts").json()["elevenlabs"]["linked"] is False
    bad = c.post("/api/accounts/elevenlabs", json={"api_key": "sk_wrong_key_123456", "plan_price_eur": 20,
                                                    "plan_credits": 121000})
    assert bad.status_code == 400 and "no aceptó la clave" in bad.json()["detail"]
    assert c.get("/api/accounts").json()["elevenlabs"]["linked"] is False  # una clave mala no se guarda
    assert c.post("/api/accounts/elevenlabs", json={"api_key": KEY}).status_code == 400  # sin precio, no
    r = c.post("/api/accounts/elevenlabs", json={"api_key": KEY, "plan_price_eur": 20, "plan_credits": 121000})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["linked"] and v["has_key"] and v["role"] == "primary" and KEY not in r.text
    assert v["subscription"]["remaining"] == 100000 and v["subscription"]["commercial_use"] is True
    assert v["params"]["default_voice_id"] == "VOZ1"
    assert v["params"]["price_per_1k_chars_eur"] == pytest.approx(20 / 121000 * 1000, abs=1e-4)
    assert c.get("/api/accounts/elevenlabs/voices").json()[0]["name"] == "Lucía"
    assert c.post("/api/accounts/elevenlabs", json={"model_id": "eleven_flash_v2_5"}).json()["params"]["model_id"] \
        == "eleven_flash_v2_5"
    reg = app.provider_system.registry
    assert reg.vault.get_all("elevenlabs")["api_key"] == KEY  # cifrada en el almacén, no en claro en la base
    assert c.delete("/api/accounts/elevenlabs").json()["linked"] is False
    assert reg.vault.get_all("elevenlabs") == {}


def test_link_higgsfield_plan_credits_and_models(env):
    _, c, cli = env
    st = c.get("/api/accounts").json()["higgsfield"]
    assert st["status"]["logged_in"] and st["status"]["credits"] == 1200 and not st["video"]["linked"]
    assert c.post("/api/accounts/higgsfield", json={"use_video": True}).status_code == 400  # sin precio, no
    r = c.post("/api/accounts/higgsfield", json={"use_video": True, "use_image": True, "plan_price_eur": 59,
                                                  "plan_credits": 1200, "video_model": "seedance_2_5",
                                                  "max_clips_per_video": 3})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["video"]["linked"] and v["video"]["role"] == "primary" and v["video"]["model"] == "seedance_2_5"
    assert v["image"]["linked"] and v["video"]["max_per_video"] == 3
    assert v["price_per_credit_eur"] == pytest.approx(59 / 1200, abs=1e-6)
    assert c.post("/api/accounts/higgsfield", json={"video_model": "no_existe"}).status_code == 400
    est = c.post("/api/accounts/higgsfield/estimate?kind=video&seconds=5").json()
    assert est["credits"] == 25 and est["eur"] == pytest.approx(25 * 59 / 1200, abs=1e-3)
    assert not any(a[:2] == ["generate", "create"] for a in cli.calls)  # estimar no gasta
    off = c.post("/api/accounts/higgsfield", json={"use_image": False}).json()
    assert off["image"]["linked"] is False and off["video"]["linked"]


def test_spend_is_never_authorized_by_linking_only_explicitly(env):
    app, c, _ = env
    c.post("/api/accounts/higgsfield", json={"use_video": True, "plan_price_eur": 59, "plan_credits": 1200})
    b = app.provider_system.budget
    assert "higgsfield_video" not in (b.get_setting("spend_authorized_providers", []) or [])
    assert c.put("/api/accounts/elevenlabs/always", json={"authorized": True}).status_code == 400  # sin vincular
    assert c.put("/api/accounts/nope/always", json={"authorized": True}).status_code == 404
    r = c.put("/api/accounts/higgsfield_video/always", json={"authorized": True}).json()
    assert r["always"] == ["higgsfield_video"]
    assert c.put("/api/accounts/higgsfield_video/always", json={"authorized": False}).json()["always"] == []


def test_install_and_login_buttons(env, monkeypatch):
    _, c, _ = env
    monkeypatch.setattr(hf, "install_cli", lambda: {"path": "/x/hf", "version": "1.2.2", "sha256": "ab"})
    assert c.post("/api/accounts/higgsfield/install").json()["installed"]["version"] == "1.2.2"
    opened = []
    monkeypatch.setattr(accounts_api, "_popen", lambda argv, **kw: opened.append(argv))
    monkeypatch.setattr(hf, "login_launch", lambda b, *a, **k: ([b, "auth", "login"], {}))
    r = c.post("/api/accounts/higgsfield/login").json()
    assert r["opened"] and opened and opened[0][1:] == ["auth", "login"]
    monkeypatch.setattr(hf, "login_launch", lambda b, *a, **k: None)
    assert c.post("/api/accounts/higgsfield/login").json() == {"opened": False, "command": f"{opened[0][0]} auth login"}
