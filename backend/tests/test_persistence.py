"""Persistencia SQLite, memoria del proyecto, copias de seguridad, logs y CLI."""
from __future__ import annotations

import json
import os

from ytauto.core.events import Event
from ytauto.core.logging_setup import redact
from ytauto.core.models import PhaseStatus, ProjectSpec
from ytauto.core.workspace import ProjectMemory, Workspace
from ytauto.db.backup import backup, restore
from ytauto.db.schema import make_engine
from ytauto.db.store import SqlStateStore
from ytauto.orchestrator.state import Approval, ProjectRecord


def test_sql_store_survives_reopen(tmp_path):
    db = tmp_path / "y.db"
    s1 = SqlStateStore(make_engine(db))
    s1.create_project(ProjectRecord(id="p1", spec=ProjectSpec(name="a", topic="b")))
    ph = s1.get_phase("p1", "script")
    ph.status, ph.scene_filter, ph.summary = PhaseStatus.COMPLETED, [1, 2], "ok"
    s1.save_phase(ph)
    s1.add_approval(Approval(project_id="p1", gate="script_approval", approved=True))
    s1.record_llm_usage("p1", "director", "creative_direction", {"duration_s": 1.2})
    s1.log_event(Event(type="phase.status", project_id="p1", data={"x": 1}))
    # "Nuevo proceso"
    s2 = SqlStateStore(make_engine(db))
    ph2 = s2.get_phase("p1", "script")
    assert ph2.status is PhaseStatus.COMPLETED and ph2.scene_filter == [1, 2]
    assert s2.get_approvals("p1")[0].approved
    assert s2.llm_usage("p1")[0]["duration_s"] == 1.2
    assert s2.events("p1")[0]["type"] == "phase.status"
    assert len(s2.list_phases("p1")) == 18


def test_duplicate_project_rejected(tmp_path):
    s = SqlStateStore(make_engine(tmp_path / "y.db"))
    rec = ProjectRecord(id="p1", spec=ProjectSpec(name="a", topic="b"))
    s.create_project(rec)
    try:
        s.create_project(rec)
        raise AssertionError("debió fallar")
    except ValueError:
        pass


def test_project_memory_persists_and_digests(tmp_path):
    ws = Workspace(tmp_path, "p1")
    m = ProjectMemory(ws)
    m.set_summary("script", "Guion de 140 palabras")
    m.add_decision("director", "Estilo cinemático")
    m2 = ProjectMemory(Workspace(tmp_path, "p1"))
    assert m2.summaries()["script"] == "Guion de 140 palabras"
    assert "cinemático" in m2.digest()
    assert len(m2.digest(max_chars=20)) <= 20


def test_workspace_blocks_path_traversal(tmp_path):
    ws = Workspace(tmp_path, "p1")
    try:
        ws.resolve_inside(tmp_path / "p1" / ".." / ".." / "etc")
        raise AssertionError("debió fallar")
    except PermissionError:
        pass
    try:
        ws.dir("../otro")
        raise AssertionError("debió fallar")
    except ValueError:
        pass


def test_backup_and_restore(tmp_path):
    db = tmp_path / "data" / "y.db"
    s = SqlStateStore(make_engine(db))
    s.create_project(ProjectRecord(id="p1", spec=ProjectSpec(name="a", topic="b")))
    projects = tmp_path / "projects"
    Workspace(projects, "p1").save("scripts", "script", {"x": 1})
    (projects / "p1" / "voice" / "s00.wav").write_bytes(b"audio")
    out = backup(db, tmp_path / "backups", projects_dir=projects)
    restored = restore(out, tmp_path / "restored")
    s2 = SqlStateStore(make_engine(restored))
    assert s2.get_project("p1").spec.topic == "b"
    assert (tmp_path / "restored" / "projects" / "p1" / "scripts" / "script.json").exists()
    assert not (tmp_path / "restored" / "projects" / "p1" / "voice" / "s00.wav").exists()  # sin medios


def test_backup_rotation(tmp_path):
    db = tmp_path / "y.db"
    SqlStateStore(make_engine(db))
    for _ in range(4):
        backup(db, tmp_path / "b", keep=2)
    assert len(list((tmp_path / "b").glob("*.tar.gz"))) == 2


def test_secrets_are_redacted_in_logs():
    text = 'api_key="sk-abcdefghijklmnop" Authorization: Bearer abcdef123456 token=xyz98765'
    out = redact(text)
    assert "abcdefghijklmnop" not in out and "abcdef123456" not in out and "xyz98765" not in out


def test_cli_offline_production(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("YTAUTO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YTAUTO_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setenv("YTAUTO_BACKUPS_DIR", str(tmp_path / "backups"))
    from ytauto.cli import main
    base = ["--offline", "--mock-providers"]
    main(base + ["new", "--name", "cli", "--topic", "las abejas", "--auto"])
    pid = json.loads(capsys.readouterr().out)["project_id"]
    main(base + ["run"])
    capsys.readouterr()
    main(base + ["status", pid])
    status = json.loads(capsys.readouterr().out)
    by = {p["phase"]: p["status"] for p in status["phases"]}
    assert by["review"] == "completed" and by["final_approval"] == "in_review"
    main(base + ["approve", pid, "final_approval"])
    main(base + ["run"])
    main(base + ["approve", pid, "publish_decision", "--note", "manual"])
    main(base + ["run"])
    capsys.readouterr()
    main(base + ["status", pid])
    assert json.loads(capsys.readouterr().out)["project"]["status"] == "completed"
    main(base + ["backup"])
    assert os.path.exists(json.loads(capsys.readouterr().out)["backup"])


def test_app_uses_persistent_registry_and_cli_manages_providers(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("YTAUTO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YTAUTO_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    from ytauto.cli import main
    main(["providers", "list"])
    listed = json.loads(capsys.readouterr().out)
    roles = {p["id"]: p["role"] for p in listed}
    assert roles["acoustic"] == "primary" and roles["proportional"] == "fallback"
    assert (tmp_path / "data" / "secrets" / "master.key").exists()
    main(["budget", "--monthly", "25"])
    assert json.loads(capsys.readouterr().out)["monthly_budget_eur"] == 25
    main(["providers", "test", "proportional"])
    assert json.loads(capsys.readouterr().out)["passed"] is True
