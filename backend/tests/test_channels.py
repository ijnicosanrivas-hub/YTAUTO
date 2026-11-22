"""Canales en paralelo, licencias de Claude por canal, entrevista del director y figuras por perfil."""
from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ytauto.agents.briefing import BASE_QUESTIONS, ask_briefing, duration_from_answer
from ytauto.api import channels_api
from ytauto.api.board import ChannelBoards
from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.channels import load_channels
from ytauto.core.events import Event
from ytauto.core.models import ProjectSpec
from ytauto.core.settings import Settings
from ytauto.llm.base import LLMRequest, LLMResponse, LLMUsage, UsageLimitError
from ytauto.llm.licenses import LicenseInput, LicenseRouter, LicenseStore, usage_stats
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    s.llm_provider = "local_draft"
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)
    return app, TestClient(create_api(app))


def _lic(c, channel="general", name="Pro A", **kw):
    r = c.post("/api/licenses", json={"name": name, "channel_id": channel, "plan": "Pro", **kw})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- canales
def test_four_channels_configured_with_profiles():
    chs = load_channels()
    assert [c.id for c in chs] == ["general", "gta6", "kids", "deportes"]
    assert [c.theme for c in chs] == ["gotham", "gta6", "kids", "deportes"]


def test_channels_file_missing_falls_back(tmp_path):
    assert [c.id for c in load_channels(tmp_path / "nada.yaml")] == ["general"]


def test_channels_api_and_theme_per_channel(env):
    _, c = env
    chs = c.get("/api/channels").json()
    assert len(chs) == 4 and all(x["director"] and x["director"]["character"] for x in chs)
    # la cara de cada canal es su jefe (el del centro de la sala): Batman en General
    assert {x["id"]: x["chief"]["character"] for x in chs}["general"] == "Batman"
    assert all("has_chief_image" in x for x in chs)
    assert all(o["chief"]["character"] for o in c.get("/api/overview").json()["channels"])
    assert c.get("/api/theme?channel=gta6").json()["id"] == "gta6"
    assert c.get("/api/theme?channel=nope").status_code == 404


def test_boards_are_independent_per_channel():
    owner = {"p1": "general", "p2": "gta6"}
    boards = ChannelBoards(["general", "gta6"], owner.get)
    boards.apply(Event(type="agent.started", project_id="p1", agent="director", phase="creative_direction"))
    assert boards.board("general").agents["director"].status == "running"
    assert boards.board("gta6").agents["director"].status == "idle"
    assert boards.apply(Event(type="agent.started", project_id=None, agent="director")) is None


def test_projects_filtered_by_channel_and_unknown_channel_rejected(env):
    _, c = env
    assert c.post("/api/projects", json={"name": "A", "topic": "medusas", "channel": "gta6"}).status_code == 201
    assert c.post("/api/projects", json={"name": "B", "topic": "medusas", "channel": "kids"}).status_code == 201
    assert c.post("/api/projects", json={"name": "C", "topic": "medusas", "channel": "marte"}).status_code == 400
    assert [p["name"] for p in c.get("/api/projects?channel=gta6").json()] == ["A"]
    ov = c.get("/api/overview").json()["channels"]
    assert {x["channel"]["id"]: x["projects"]["total"] for x in ov} == {"general": 0, "gta6": 1, "kids": 1, "deportes": 0}


# ---------------------------------------------------------------- licencias
def test_license_crud_never_returns_secret(env):
    app, c = env
    lic = _lic(c, kind="api_key", api_key="sk-ant-secreta-1234567890")
    assert "api_key" not in lic and lic["secret_hint"].endswith("7890")
    listed = c.get("/api/licenses").json()
    assert "secreta" not in str(listed)
    assert app.licenses.secret(lic["id"]) == "sk-ant-secreta-1234567890"
    assert c.post("/api/licenses", json={"name": "x", "channel_id": "general", "kind": "api_key"}).status_code == 400
    assert c.post("/api/licenses", json={"name": "x", "channel_id": "luna"}).status_code == 404
    assert c.delete(f"/api/licenses/{lic['id']}").status_code == 204


def test_session_license_gets_own_config_dir(env):
    app, c = env
    lic = _lic(c)
    assert lic["kind"] == "claude_session" and lic["config_dir"].endswith(lic["id"])


def test_claude_slots_grow_with_licenses(env):
    app, c = env
    assert app.queue.lanes()["claude"].concurrency == 1
    for i, ch in enumerate(["general", "gta6", "kids", "deportes"]):
        _lic(c, channel=ch, name=f"L{i}")
    assert app.queue.lanes()["claude"].concurrency == 4
    # a mano no se puede pasar de una llamada por cuenta
    assert c.put("/api/queue/concurrency", json={"lane": "claude", "concurrency": 8}).json()["concurrency"] == 4


def _router(tmp_path, handler):
    from sqlalchemy import create_engine

    from cryptography.fernet import Fernet
    engine = create_engine(f"sqlite:///{tmp_path / 'r.db'}")
    store = LicenseStore(engine, Fernet.generate_key(), tmp_path)
    specs: dict[str, ProjectSpec] = {}
    made = []

    def factory(lic, secret):
        made.append((lic.id, secret))
        return ScriptedLLM({"director": handler})

    router = LicenseRouter(store, ScriptedLLM({"director": [{"ok": "default"}]}), factory, specs.__getitem__)
    return router, store, specs, made


def test_router_uses_assigned_license_then_channel_default(tmp_path):
    router, store, specs, _ = _router(tmp_path, [{"ok": "lic"}])
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    b = store.create(LicenseInput(name="B", channel_id="kids"))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    req = LLMRequest(agent="director", task="t", output_schema={}, project_id="p")
    assert router.complete(req).usage.license_id == a.id
    specs["p"].license_map = {"director": b.id}  # el usuario elige una licencia de otro canal
    assert router.complete(req).usage.license_id == b.id
    specs["q"] = ProjectSpec(name="x", topic="y", channel="deportes")  # canal sin licencias → sesión por defecto
    assert router.complete(req.model_copy(update={"project_id": "q"})).usage.license_id is None


def test_router_marks_only_that_license_as_limited(tmp_path):
    router, store, specs, _ = _router(tmp_path, [UsageLimitError("usage limit reached|9999999999", resets_at="9999999999")])
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    req = LLMRequest(agent="director", task="t", output_schema={}, project_id="p")
    with pytest.raises(UsageLimitError) as e:
        router.complete(req)
    assert e.value.license_id == a.id and store.get(a.id).limited_now()
    # mientras siga agotada no se vuelve a llamar a Claude con ella
    with pytest.raises(UsageLimitError):
        router.complete(req)
    store.clear_limit(a.id)
    assert not store.get(a.id).limited_now()


def test_router_skips_limited_license_within_same_channel(tmp_path):
    router, store, specs, _ = _router(tmp_path, [{"ok": 1}])
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    b = store.create(LicenseInput(name="B", channel_id="gta6"))
    store.mark_limited(a.id, str(int(time.time()) + 3600), "límite")
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    assert router.resolve("p", "director").id == b.id


def test_expired_limit_clears_itself(tmp_path):
    router, store, specs, _ = _router(tmp_path, [{"ok": 1}])
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    store.mark_limited(a.id, str(int(time.time()) - 5), "límite")
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    req = LLMRequest(agent="director", task="t", output_schema={}, project_id="p")
    assert router.complete(req).usage.license_id == a.id
    assert not store.get(a.id).is_limited


def test_api_key_license_passes_decrypted_secret_to_factory(tmp_path):
    router, store, specs, made = _router(tmp_path, [{"ok": 1}])
    a = store.create(LicenseInput(name="API", channel_id="gta6", kind="api_key", api_key="sk-ant-abcdefghijkl"))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    router.complete(LLMRequest(agent="director", task="t", output_schema={}, project_id="p"))
    assert made == [(a.id, "sk-ant-abcdefghijkl")]


def test_cli_provider_receives_license_env():
    from ytauto.llm.claude_cli import ClaudeCodeCLIProvider
    seen = {}

    def runner(cmd, stdin, timeout, cwd, env=None):
        seen["env"] = env
        import subprocess
        return subprocess.CompletedProcess(cmd, 0, '{"structured_output": {"a": 1}, "usage": {"input_tokens": 5, '
                                                   '"output_tokens": 7, "cache_read_input_tokens": 3}}', "")

    p = ClaudeCodeCLIProvider(runner=runner, env={"CLAUDE_CONFIG_DIR": "/x"})
    r = p.complete(LLMRequest(agent="director", task="t", output_schema={}))
    assert seen["env"] == {"CLAUDE_CONFIG_DIR": "/x"} and r.usage.cache_read_tokens == 3


def test_usage_stats_per_license():
    now = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    from ytauto.llm.licenses import License
    lic = License(id="lic_aaaaaa", name="A", channel_id="gta6", kind="claude_session", monthly_token_limit=1000)
    usage = [
        {"project_id": "p", "agent": "director", "at": "2026-11-22T10:00:00+00:00", "license_id": "lic_aaaaaa",
         "input_tokens": 100, "output_tokens": 50, "duration_s": 2},
        {"project_id": "p", "agent": "editor", "at": "2026-11-10T10:00:00+00:00", "license_id": "lic_aaaaaa",
         "input_tokens": 200, "output_tokens": 0},
        {"project_id": "q", "agent": "director", "at": "2026-11-22T09:00:00+00:00", "input_tokens": 7},
    ]
    st = usage_stats([lic], usage, {"p": "gta6", "q": "general"}, now=now)
    a = st["licenses"][0]
    assert a["tokens"] == {"today": 150, "d7": 150, "d30": 350, "month": 350}
    assert a["usage_pct"] == 35.0 and a["by_agent"] == {"director": 150, "editor": 200}
    assert a["by_channel"] == {"gta6": 350} and a["daily"][-1] == {"day": "2026-11-22", "tokens": 150}
    assert st["default"]["tokens"]["today"] == 7 and st["totals"]["tokens_month"] == 357


def test_project_usage_is_tagged_with_license(env):
    app, c = env
    lic = _lic(c, channel="gta6")
    p = c.post("/api/projects", json={"name": "A", "topic": "medusas", "channel": "gta6"}).json()["project"]["id"]
    app.worker.run_until_idle(max_ticks=3)
    tagged = [u for u in app.store.llm_usage(p) if u.get("license_id") == lic["id"]]
    assert tagged
    stats = c.get("/api/licenses?channel=gta6").json()["licenses"][0]
    assert stats["calls"]["total"] >= 1 and stats["by_channel"].get("gta6", 0) >= 0


def test_limit_of_one_license_does_not_pause_other_channels(env):
    app, c = env
    lic = _lic(c, channel="gta6")
    p = c.post("/api/projects", json={"name": "A", "topic": "medusas", "channel": "gta6"}).json()["project"]["id"]
    app.licenses.mark_limited(lic["id"], str(int(time.time()) + 3600), "usage limit")
    app.worker.run_until_idle(max_ticks=3)
    assert app.store.get_project(p).status.value == "blocked"
    assert app.queue.lanes()["claude"].paused is False  # los demás canales siguen
    # El usuario reasigna el agente a una licencia de otro canal y el proyecto se reanuda
    other = _lic(c, channel="kids", name="Kids")
    r = c.put(f"/api/projects/{p}/licenses", json={"license_map": {"chief": other["id"], "director": other["id"]}}).json()
    assert r["resumed"] is True and app.store.get_project(p).status.value == "active"


def test_license_plan_endpoint(env):
    _, c = env
    lic = _lic(c, channel="kids")
    plan = c.get("/api/licenses/plan?channel=kids").json()["plan"]
    assert set(plan.values()) == {lic["id"]} and len(plan) == 9
    assert set(c.get("/api/licenses/plan?channel=deportes").json()["plan"].values()) == {None}


def test_create_project_rejects_unknown_license(env):
    _, c = env
    r = c.post("/api/projects", json={"name": "A", "topic": "m", "license_map": {"director": "lic_noexiste"}})
    assert r.status_code == 400


# ---------------------------------------------------------------- entrevista del director
def test_briefing_falls_back_to_base_questions(env):
    _, c = env
    r = c.post("/api/briefing", json={"channel": "general", "idea": "algo de tiburones"}).json()
    assert r["source"] == "base" and {q["id"] for q in r["questions"]} >= {"duration", "quality"}
    assert r["director"]["character"]


def test_briefing_with_claude_always_includes_duration_and_quality():
    llm = ScriptedLLM({"director": [{"reading": "Entiendo...", "questions": [
        {"id": "angle", "question": "¿Qué ángulo quieres?", "kind": "text"},
        {"id": "hero", "question": "¿Quién protagoniza?", "kind": "text"},
        {"id": "tone", "question": "¿Qué tono?", "kind": "choice", "options": ["a", "b"]},
        {"id": "end", "question": "¿Cómo termina?", "kind": "text"}]}]})
    out = ask_briefing(llm, "sonnet", "tiburones", "General")
    assert out.source == "claude" and [q.id for q in out.questions][:2] == ["duration", "quality"]


def test_briefing_invalid_claude_output_uses_base():
    out = ask_briefing(ScriptedLLM({"director": [{"nada": 1}]}), "sonnet", "x", "General")
    assert out.source == "base" and len(out.questions) == len(BASE_QUESTIONS)


def test_duration_from_answer():
    assert duration_from_answer("60 s") == 60
    assert duration_from_answer("unos 75 segundos") == 75
    assert duration_from_answer("2 minutos") is None and duration_from_answer("") is None


def test_brief_answers_reach_the_director(env):
    app, c = env
    seen = {}
    original = app.router.default.complete

    def spy(req):
        if req.agent == "director":
            seen["brief"] = req.context["user_request"].get("brief")
        return original(req)

    app.router.default.complete = spy
    spec = {"name": "A", "topic": "medusas", "brief": [{"question": "¿Tono?", "answer": "Misterio"}]}
    c.post("/api/projects", json=spec)
    app.worker.run_until_idle(max_ticks=3)
    assert seen["brief"] == [{"question": "¿Tono?", "answer": "Misterio"}]


# ---------------------------------------------------------------- figuras por perfil
def test_upload_profile_figure(env, tmp_path, monkeypatch):
    from PIL import Image
    _, c = env
    monkeypatch.setattr(channels_api, "PROFILES_DIR", tmp_path / "perfiles")
    img = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (50, 60, 250, 380))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = c.put("/api/profiles/gta6/figures/director", content=buf.getvalue())
    assert r.status_code == 200 and r.json()["w"] == 200 and r.json()["h"] == 320  # márgenes recortados
    assert c.get("/api/profiles/gta6/figures").json()["director"]["h"] == 320
    assert c.get("/api/profiles/gta6/figures/director.png").status_code == 200
    assert c.put("/api/profiles/gta6/figures/director", content=b"no soy imagen").status_code == 400
    assert c.put("/api/profiles/gta6/figures/nadie", content=buf.getvalue()).status_code == 404
    assert c.get("/api/profiles/..%2F/figures").status_code == 404


def test_usage_response_contains_license(tmp_path):
    router, store, specs, _ = _router(tmp_path, [{"ok": 1}])
    assert isinstance(router.complete(LLMRequest(agent="director", task="t", output_schema={})), LLMResponse)
    assert LLMUsage().license_id is None
