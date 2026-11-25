"""Monitor de tokens en vivo por licencia: ventanas, ritmo, límite observado y freno de gasto."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.models import ProjectSpec
from ytauto.core.settings import Settings
from ytauto.db.schema import init_db
from ytauto.llm.base import LLMRequest, UsageLimitError
from ytauto.llm.licenses import License, LicenseInput, LicenseRouter, LicenseStore, live_usage
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def call(minutes_ago: float, tokens: int = 1000, usd: float = 0.0, agent: str = "director") -> dict:
    return {"at": (NOW - timedelta(minutes=minutes_ago)).isoformat(), "agent": agent, "input_tokens": tokens,
            "output_tokens": 0, "cost_usd_equivalent": usd}


def lic(**kw) -> License:
    return License(id="lic_aaaaaa", name="A", channel_id="gta6", kind="claude_session", **kw)


def test_windows_rate_and_when_the_window_frees():
    rows = [call(5), call(10), call(200), call(60 * 24 * 2), call(60 * 24 * 9)]
    live = live_usage(lic(budget_5h_tokens=10_000), rows, NOW)
    assert live["used_5h"] == 3000 and live["used_week"] == 4000 and live["calls_5h"] == 3
    assert live["burn_per_min"] == pytest.approx(2000 / 15, abs=0.1)
    assert live["remaining_5h"] == 7000 and live["pct_5h"] == 30.0 and live["status"] == "ok"
    assert live["eta_min"] == pytest.approx(7000 / (2000 / 15), abs=0.2)
    # la ventana se libera cuando la llamada más antigua de las últimas 5 h cumple 5 h
    assert live["window_frees_at"] == (NOW - timedelta(minutes=200) + timedelta(hours=5)).isoformat()
    assert sum(live["spark"]) == 2000 and len(live["spark"]) == 24 and live["recent"][0]["tokens"] == 1000


def test_warning_and_brake_by_window_week_and_money():
    assert live_usage(lic(budget_5h_tokens=1200), [call(5)], NOW)["status"] == "aviso"  # 83 %
    b = live_usage(lic(budget_5h_tokens=1000), [call(5), call(30)], NOW)
    assert b["status"] == "freno" and "5 h" in b["brake"]["reason"]
    assert b["brake"]["until"] == (NOW - timedelta(minutes=30) + timedelta(hours=5)).timestamp()
    w = live_usage(lic(budget_week_tokens=1500), [call(60 * 24), call(60 * 48)], NOW)
    assert w["status"] == "freno" and "semana" in w["brake"]["reason"]
    m = live_usage(lic(budget_month_usd=1.0), [call(60, usd=0.6), call(120, usd=0.5)], NOW)
    assert m["status"] == "freno" and m["pct_usd"] == 110.0
    assert m["brake"]["until"] == datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp()


def test_observed_limit_is_used_when_no_budget_is_set():
    live = live_usage(lic(observed_5h_tokens=4000), [call(5, 1000)], NOW)
    assert live["limit_5h"] == 4000 and live["limit_5h_source"] == "observado" and live["remaining_5h"] == 3000


def test_no_limits_means_no_brake_and_no_percent():
    live = live_usage(lic(), [call(5)], NOW)
    assert live["pct_5h"] is None and live["brake"] is None and live["status"] == "ok"
    assert live_usage(None, [], NOW)["used_5h"] == 0


def _router(tmp_path, handler, rows):
    store = LicenseStore(create_engine(f"sqlite:///{tmp_path / 'r.db'}"), Fernet.generate_key(), tmp_path)
    specs: dict[str, ProjectSpec] = {}
    provider = ScriptedLLM({"director": handler})
    events: list[dict] = []
    router = LicenseRouter(store, ScriptedLLM({"director": [{"ok": 1}]}), lambda lic, secret: provider, specs.__getitem__,
                           usage_rows=lambda lid, since: list(rows), on_event=events.append)
    return router, store, specs, provider, events


def test_brake_stops_before_spending_and_does_not_call_claude(tmp_path):
    now_rows = [{"at": datetime.now(timezone.utc).isoformat(), "input_tokens": 5000, "license_id": "x"}]
    router, store, specs, provider, events = _router(tmp_path, [{"ok": 1}], now_rows)
    a = store.create(LicenseInput(name="A", channel_id="gta6", budget_5h_tokens=4000))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    with pytest.raises(UsageLimitError) as e:
        router.complete(LLMRequest(agent="director", task="t", output_schema={}, project_id="p"))
    assert e.value.license_id == a.id and provider.calls == []  # no se gastó nada
    assert store.get(a.id).limited_now() and "Freno de gasto" in store.get(a.id).limited_reason
    assert events[-1]["phase"] == "brake"


def test_real_limit_records_the_observed_limit(tmp_path):
    rows = [{"at": datetime.now(timezone.utc).isoformat(), "input_tokens": 7777}]
    router, store, specs, _, _ = _router(tmp_path, [UsageLimitError("usage limit reached")], rows)
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    with pytest.raises(UsageLimitError):
        router.complete(LLMRequest(agent="director", task="t", output_schema={}, project_id="p"))
    assert store.get(a.id).observed_5h_tokens == 7777


def test_live_events_on_start_and_end(tmp_path):
    router, store, specs, _, events = _router(tmp_path, [{"ok": 1}], [])
    a = store.create(LicenseInput(name="A", channel_id="gta6"))
    specs["p"] = ProjectSpec(name="x", topic="y", channel="gta6")
    router.complete(LLMRequest(agent="director", task="t", output_schema={}, project_id="p"))
    assert [e["phase"] for e in events] == ["start", "end"]
    assert events[0]["in_flight"] == 1 and events[1]["in_flight"] == 0 and events[0]["license_id"] == a.id


def test_old_database_gets_the_new_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as c:  # tabla de licencias de la versión 3, sin las columnas de límites
        c.execute(text("CREATE TABLE licenses (id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, channel_id VARCHAR NOT NULL, "
                       "kind VARCHAR NOT NULL, plan VARCHAR NOT NULL, config_dir VARCHAR, secret_cipher TEXT, secret_hint VARCHAR, "
                       "monthly_token_limit INTEGER, enabled BOOLEAN NOT NULL, limited_until FLOAT, limited_reason TEXT, "
                       "is_limited BOOLEAN NOT NULL, last_used_at VARCHAR, notes TEXT, created_at VARCHAR NOT NULL)"))
    init_db(engine)
    with engine.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(licenses)"))}
    assert {"budget_5h_tokens", "budget_week_tokens", "budget_month_usd", "observed_5h_tokens"} <= cols


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    s.llm_provider = "local_draft"
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)
    return app, TestClient(create_api(app))


def test_live_endpoint_counts_real_calls(env):
    app, c = env
    lid = c.post("/api/licenses", json={"name": "Pro", "channel_id": "gta6", "budget_5h_tokens": 1_000_000}).json()["id"]
    c.post("/api/projects", json={"name": "A", "topic": "medusas", "channel": "gta6"})
    app.worker.run_until_idle(max_ticks=3)
    live = c.get("/api/licenses/live").json()
    me = next(x for x in live["licenses"] if x["id"] == lid)
    assert me["calls_5h"] >= 1 and me["status"] == "ok" and me["limit_5h"] == 1_000_000 and me["in_flight"] == 0
    assert live["totals"]["stopped"] == 0 and live["warn_pct"] == 80


def test_budgets_are_saved_from_the_api(env):
    _, c = env
    r = c.post("/api/licenses", json={"name": "Pro", "channel_id": "kids", "budget_5h_tokens": 500000,
                                      "budget_week_tokens": 3000000, "budget_month_usd": 20}).json()
    assert (r["budget_5h_tokens"], r["budget_week_tokens"], r["budget_month_usd"]) == (500000, 3000000, 20.0)


def test_raising_the_limit_releases_a_braked_license(env):
    app, c = env
    lid = c.post("/api/licenses", json={"name": "Pro", "channel_id": "gta6"}).json()["id"]
    app.licenses.mark_limited(lid, str(int(datetime.now(timezone.utc).timestamp()) + 3600), "Freno de gasto (ventana de 5 h)")
    r = c.put(f"/api/licenses/{lid}/limits", json={"budget_5h_tokens": 9_000_000, "budget_week_tokens": 0}).json()
    assert r["budget_5h_tokens"] == 9_000_000 and r["budget_week_tokens"] is None and r["is_limited"] is False
    # un corte REAL de Claude no se levanta subiendo tu límite
    app.licenses.mark_limited(lid, None, "usage limit reached")
    assert c.put(f"/api/licenses/{lid}/limits", json={"budget_5h_tokens": 1}).json()["is_limited"] is True
