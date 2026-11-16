"""Worker + cola + orquestador + SQLite: producción completa, límites, reintentos, recuperación."""
from __future__ import annotations

import pytest

from ytauto.core.errors import ProviderError
from ytauto.core.models import PhaseStatus, ProjectSpec, ProjectStatus
from ytauto.db.schema import make_engine
from ytauto.db.store import SqlStateStore
from ytauto.llm.base import UsageLimitError
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM
from ytauto.orchestrator.orchestrator import Orchestrator, OrchestratorSettings
from ytauto.providers.interfaces import ProviderCategory
from ytauto.queue.task_queue import TaskQueue
from ytauto.queue.worker import ProductionWorker, parse_resume_at


class Clock:
    def __init__(self):
        self.t = 1_700_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path, gateway):
    clock = Clock()

    def build(llm=None, providers=None):
        engine = make_engine(tmp_path / "ytauto.db")
        store = SqlStateStore(engine)
        queue = TaskQueue(engine, clock=clock, lease_s=600)
        orch = Orchestrator(store=store, llm=llm or LocalDraftLLM(), providers=providers or gateway,
                            settings=OrchestratorSettings(projects_dir=tmp_path / "projects"))
        return orch, queue, ProductionWorker(orch, queue, backoff_s=(10, 20))

    return build, clock


def spec(**kw):
    base = dict(name="Prueba", topic="los volcanes", duration_s=60, require_script_approval=False)
    return ProjectSpec(**{**base, **kw})


def test_full_production_through_queue(env):
    build, _ = env
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    worker.schedule(pid)
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "final_approval").status is PhaseStatus.IN_REVIEW
    orch.approve(pid, "final_approval")
    worker.schedule(pid)
    worker.run_until_idle()
    orch.approve(pid, "publish_decision", note="manual")
    worker.schedule(pid)
    worker.run_until_idle()
    assert orch.store.get_project(pid).status is ProjectStatus.COMPLETED
    lanes_used = {t.lane for t in queue.tasks(pid)}
    assert {"claude", "media", "none"} <= lanes_used
    # Ninguna fase se ejecutó dos veces
    assert all(ph.attempts <= 1 for ph in orch.store.list_phases(pid))


def test_usage_limit_pauses_claude_lane_and_auto_resumes(env):
    build, clock = env
    draft = LocalDraftLLM()
    state = {"limited": True}

    def director(req):
        if state["limited"]:
            return UsageLimitError("Claude AI usage limit reached", resets_at=str(int(clock.t + 3600)))
        return draft.complete(req).data

    orch, queue, worker = build(llm=ScriptedLLM({"director": director}, fallback=draft))
    p1 = orch.create_project(spec(name="uno"))
    worker.schedule(p1)
    worker.run_until_idle()
    lane = queue.lanes()["claude"]
    assert lane.paused and lane.resume_at == clock.t + 3600
    assert orch.store.get_project(p1).status is ProjectStatus.BLOCKED
    # Un segundo proyecto no lanza tareas de Claude mientras dure el límite
    p2 = orch.create_project(spec(name="dos"))
    worker.schedule(p2)
    worker.run_until_idle()
    assert orch.store.get_phase(p2, "creative_direction").attempts == 0
    # Pasa la ventana de uso
    state["limited"] = False
    clock.t += 3601
    worker.run_until_idle()
    worker.schedule_all()
    worker.run_until_idle()
    for pid in (p1, p2):
        assert orch.store.get_phase(pid, "final_approval").status is PhaseStatus.IN_REVIEW


def test_unknown_reset_time_requires_manual_resume(env):
    build, clock = env
    orch, queue, worker = build(llm=ScriptedLLM({"director": [UsageLimitError("limit reached")]},
                                                fallback=LocalDraftLLM()))
    pid = orch.create_project(spec())
    worker.schedule(pid)
    worker.run_until_idle()
    clock.t += 10 * 3600
    worker.run_until_idle()
    assert queue.lanes()["claude"].paused  # no reintenta a ciegas
    worker.orch.llm = LocalDraftLLM()
    worker.resume_claude()
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "final_approval").status is PhaseStatus.IN_REVIEW


def test_transient_provider_error_is_retried_with_backoff(env, mock_providers):
    build, clock = env
    tts = mock_providers[ProviderCategory.TTS]
    original = tts.synthesize
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ProviderError("mock_tts", "timeout", transient=True)
        return original(req)

    tts.synthesize = flaky
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    worker.schedule(pid)
    worker.run_until_idle()
    voice = orch.store.get_phase(pid, "voice")
    assert voice.status is PhaseStatus.PENDING  # esperando backoff
    clock.t += 11
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "voice").status is PhaseStatus.COMPLETED
    assert orch.store.get_phase(pid, "voice").attempts == 2


def test_permanent_error_stops_project(env, mock_providers):
    build, _ = env

    def broken(req):
        raise ProviderError("mock_tts", "voz no válida", transient=False)

    mock_providers[ProviderCategory.TTS].synthesize = broken
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    worker.schedule(pid)
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "voice").status is PhaseStatus.ERROR
    assert orch.store.get_project(pid).status is ProjectStatus.ERROR
    assert any(t.status == "failed" for t in queue.tasks(pid))


def test_restart_recovers_interrupted_phase_without_repeating(env):
    build, _ = env
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    worker.schedule(pid)
    for _ in range(5):
        worker.tick()
    # Simula caída: una tarea arrendada y su fase en 'running'
    nxt = orch.next_phase(pid)
    queue.claim(nxt.queue, "worker-muerto")
    rec = orch.store.get_phase(pid, nxt.id)
    rec.status = PhaseStatus.RUNNING
    orch.store.save_phase(rec)
    done_before = {ph.phase: ph.attempts for ph in orch.store.list_phases(pid) if ph.status.is_done}
    # Nuevo proceso
    orch2, queue2, worker2 = build()
    worker2.recover_on_startup()
    worker2.run_until_idle()
    assert orch2.store.get_phase(pid, "final_approval").status is PhaseStatus.IN_REVIEW
    for phase, attempts in done_before.items():
        assert orch2.store.get_phase(pid, phase).attempts == attempts


def test_schedule_does_not_duplicate(env):
    build, _ = env
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    ids = {worker.schedule(pid) for _ in range(5)}
    assert len(ids) == 1 and len(queue.tasks(pid)) == 1


def test_paused_project_is_not_dispatched(env):
    build, _ = env
    orch, queue, worker = build()
    pid = orch.create_project(spec())
    worker.schedule(pid)
    orch.pause(pid)
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "intake").attempts == 0
    orch.resume(pid)
    worker.schedule(pid)
    worker.run_until_idle()
    assert orch.store.get_phase(pid, "intake").attempts == 1


def test_parse_resume_at():
    assert parse_resume_at("1700003600") == 1700003600.0
    assert parse_resume_at("5pm (Europe/Madrid)") is None
    assert parse_resume_at(None) is None


def test_run_forever_threaded_loop(tmp_path, gateway):
    import threading
    import time as _t
    engine = make_engine(tmp_path / "rf.db")
    store = SqlStateStore(engine)
    queue = TaskQueue(engine)
    orch = Orchestrator(store=store, llm=LocalDraftLLM(), providers=gateway,
                        settings=OrchestratorSettings(projects_dir=tmp_path / "projects"))
    worker = ProductionWorker(orch, queue)
    pid = orch.create_project(spec())
    th = threading.Thread(target=worker.run_forever, kwargs={"poll_s": 0.02}, daemon=True)
    th.start()
    deadline = _t.time() + 30
    while _t.time() < deadline and store.get_phase(pid, "final_approval").status is not PhaseStatus.IN_REVIEW:
        _t.sleep(0.05)
    worker.stop()
    th.join(timeout=5)
    assert store.get_phase(pid, "final_approval").status is PhaseStatus.IN_REVIEW
    assert not th.is_alive()
