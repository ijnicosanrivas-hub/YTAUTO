"""API REST + WebSocket de la sala de producción (sin Claude real ni costes)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.settings import Settings
from ytauto.llm.mock import LocalDraftLLM


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)
    reg = app.provider_system.registry
    # Proveedores simulados como principales: rápido y sin dependencias del sistema
    for adapter, cat in (("mock_image", "image"), ("mock_tts", "tts"), ("mock_music", "music"),
                         ("mock_sfx", "sfx"), ("mock_render", "rendering"), ("mock_publisher", "publishing")):
        reg.add(adapter)
        reg.set_primary(cat, adapter)
    return app, TestClient(create_api(app))


SPEC = {"name": "API", "topic": "las medusas", "duration_s": 45, "require_script_approval": True}


def test_health_and_dashboard(env):
    app, c = env
    assert c.get("/api/health").json()["ok"] is True
    d = c.get("/api/dashboard").json()
    assert len(d["agents"]) == 9 and d["projects"]["total"] == 0


def test_project_lifecycle_and_approvals(env):
    app, c = env
    r = c.post("/api/projects", json=SPEC)
    assert r.status_code == 201
    pid = r.json()["project"]["id"]
    assert c.post("/api/projects", json={**SPEC, "duration_s": 120}).status_code == 422  # validación
    app.worker.run_until_idle()
    v = c.get(f"/api/projects/{pid}").json()
    assert v["waiting_approval"] == ["script_approval"]
    # Aprobación prematura de otra puerta → 409
    assert c.post(f"/api/projects/{pid}/approve", json={"gate": "final_approval"}).status_code == 409
    assert c.post(f"/api/projects/{pid}/approve", json={"gate": "script_approval"}).status_code == 200
    app.worker.run_until_idle()
    assert c.get(f"/api/projects/{pid}").json()["waiting_approval"] == ["final_approval"]
    arts = c.get(f"/api/projects/{pid}/artifacts").json()
    assert arts["script"]["scenes"] and arts["review"]["score"] >= 0 and arts["preview"]
    lst = c.get("/api/projects").json()
    assert lst[0]["id"] == pid and 0 < lst[0]["progress"] < 1


def test_files_are_served_and_traversal_blocked(env):
    app, c = env
    pid = c.post("/api/projects", json={**SPEC, "require_script_approval": False}).json()["project"]["id"]
    app.worker.run_until_idle()
    assert c.get(f"/api/projects/{pid}/files/scripts/script.json").status_code == 200
    assert c.get(f"/api/projects/{pid}/files/../../data/y.db").status_code in (403, 404)
    assert c.get(f"/api/projects/{pid}/files/%2e%2e/%2e%2e/data/y.db").status_code in (403, 404)


def test_agents_board_reflects_real_events(env):
    app, c = env
    before = {a["name"]: a for a in c.get("/api/agents").json()["agents"]}
    assert all(a["runs"] == 0 for a in before.values())
    c.post("/api/projects", json={**SPEC, "require_script_approval": False})
    app.worker.run_until_idle()
    data = c.get("/api/agents").json()
    agents = {a["name"]: a for a in data["agents"]}
    assert agents["director"]["runs"] == 1 and agents["director"]["llm_calls"] >= 1
    assert agents["editor"]["runs"] == 2  # montaje + render
    assert agents["publisher"]["runs"] == 0  # aún no ha llegado su turno
    assert any(l["kind"] == "control" for l in data["links"]) and any(l["kind"] == "flow" for l in data["links"])


def test_board_rebuilds_after_restart(env, tmp_path):
    app, c = env
    c.post("/api/projects", json={**SPEC, "require_script_approval": False})
    app.worker.run_until_idle()
    c2 = TestClient(create_api(app))  # nuevo servidor sobre la misma base de datos
    agents = {a["name"]: a for a in c2.get("/api/agents").json()["agents"]}
    assert agents["director"]["runs"] == 1 and agents["director"]["status"] == "idle"


def test_websocket_streams_live_events(env):
    app, c = env
    with c.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and len(hello["agents"]) == 9
        c.post("/api/projects", json=SPEC)
        app.worker.tick()
        msg = ws.receive_json()
        assert msg["type"] == "event" and msg["event"]["type"]


def test_providers_panel_never_exposes_secrets(env):
    app, c = env
    r = c.post("/api/providers", json={"adapter": "mock_paid_image"})
    assert r.status_code == 201
    r = c.put("/api/providers/mock_paid_image/credentials", json={"key": "api_key", "value": "sk-very-secret-9876"})
    assert r.json()["hint"] == "••••9876"
    body = c.get("/api/providers").text
    assert "very-secret" not in body and "••••9876" in body
    assert c.post("/api/providers/mock_tts/test").json()["passed"] is True
    assert c.post("/api/providers", json={"adapter": "no_existe"}).status_code == 400
    r = c.post("/api/providers/order", json={"category": "image", "ids": ["procedural_images", "mock_image"]})
    assert r.status_code == 200 and r.json()[0]["id"] == "procedural_images"
    assert c.patch("/api/providers/mock_tts", json={"enabled": False}).json()["enabled"] is False
    assert len(c.get("/api/providers/catalog").json()) > 5


def test_budget_and_models_panels(env):
    app, c = env
    b = c.put("/api/budget", json={"monthly_budget_eur": 20, "warn_fraction": 0.7}).json()
    assert b["summary"]["monthly_budget_eur"] == 20 and b["warn_fraction"] == 0.7
    assert c.put("/api/budget", json={"monthly_budget_eur": -1}).status_code == 422
    m = c.put("/api/models", json={"agents": {"director": "opus"}}).json()
    assert m["config"]["agents"]["director"] == "opus" and app.models.for_agent("director") == "opus"
    assert c.put("/api/models", json={"agents": {"director": "gpt-4"}}).status_code == 400
    assert c.put("/api/models", json={"agents": {"nadie": "sonnet"}}).status_code == 400
    # Persisten tras reiniciar
    app2 = build_app(app.settings, llm=LocalDraftLLM(), include_mock_providers=True)
    assert app2.models.for_agent("director") == "opus"


def test_queue_controls(env):
    app, c = env
    q = c.get("/api/queue").json()
    assert q["lanes"]["claude"]["concurrency"] == 1
    assert c.put("/api/queue/concurrency", json={"lane": "claude", "concurrency": 8}).json()["concurrency"] == 2
    app.queue.pause_lane("claude", "Límite de uso")
    assert c.get("/api/queue").json()["lanes"]["claude"]["paused"] is True
    assert c.post("/api/queue/claude/resume").json()["lanes"]["claude"]["paused"] is False


def test_pause_resume_cancel_redo(env):
    app, c = env
    pid = c.post("/api/projects", json={**SPEC, "require_script_approval": False}).json()["project"]["id"]
    assert c.post(f"/api/projects/{pid}/pause").json()["project"]["status"] == "paused"
    assert c.post(f"/api/projects/{pid}/resume").json()["project"]["status"] == "active"
    app.worker.run_until_idle()
    r = c.post(f"/api/projects/{pid}/redo", json={"scenes": [1], "reason": "otra imagen"})
    assert r.status_code == 200
    app.worker.run_until_idle()
    assert c.get(f"/api/projects/{pid}").json()["waiting_approval"] == ["final_approval"]
    assert c.post(f"/api/projects/{pid}/cancel").json()["project"]["status"] == "cancelled"
    assert c.get("/api/projects/nope").status_code == 404


def test_library_lists_assets_with_license(env):
    app, c = env
    c.post("/api/projects", json={**SPEC, "require_script_approval": False})
    app.worker.run_until_idle()
    assets = c.get("/api/library").json()["assets"]
    assert assets and all(a["license"]["name"] != "unknown" and a["file"] for a in assets)


def test_token_protection(env):
    app, _ = env
    c = TestClient(create_api(app, token="s3cret"))
    assert c.get("/api/projects").status_code == 401
    assert c.get("/api/projects", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert c.get("/api/health").status_code == 200  # salud siempre accesible
    with pytest.raises(Exception):
        with c.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_websocket_disconnect_is_detected_and_client_removed(env):
    """Regresión: un cliente desconectado no debe quedar registrado (bloqueaba el apagado)."""
    import time
    app, c = env
    with c.websocket_connect("/ws") as ws:
        ws.receive_json()
    time.sleep(0.2)
    # Tras desconectar, los eventos no deben fallar ni acumularse para ese cliente
    app.events.emit("phase.status", project_id="x", phase="intake", data={"status": "running"})
    with c.websocket_connect("/ws") as ws2:
        assert ws2.receive_json()["type"] == "hello"
