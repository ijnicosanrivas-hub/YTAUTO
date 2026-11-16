"""Cola centralizada: idempotencia, concurrencia, pausa por límites, leases y reintentos."""
from __future__ import annotations

import threading

import pytest

from ytauto.db.schema import make_engine
from ytauto.queue.task_queue import TaskQueue


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def queue(tmp_path, clock):
    return TaskQueue(make_engine(tmp_path / "q.db"), clock=clock, lease_s=60)


def test_enqueue_is_idempotent(queue):
    """Misma clave o misma (proyecto, fase) activa → una sola tarea."""
    a = queue.enqueue("p1", "script", "claude", "p1:script:0")
    b = queue.enqueue("p1", "script", "claude", "p1:script:0")
    assert a == b and len(queue.tasks()) == 1


def test_claude_lane_concurrency_defaults_to_one(queue):
    queue.enqueue("p1", "script", "claude", "k1")
    queue.enqueue("p2", "script", "claude", "k2")
    assert queue.claim("claude", "w") is not None
    assert queue.claim("claude", "w") is None  # solo una tarea de Claude a la vez


def test_claude_concurrency_is_capped(queue):
    assert queue.set_concurrency("claude", 10) == 2  # máximo configurado
    queue.enqueue("p1", "a", "claude", "k1")
    queue.enqueue("p2", "a", "claude", "k2")
    queue.enqueue("p3", "a", "claude", "k3")
    assert queue.claim("claude", "w") and queue.claim("claude", "w")
    assert queue.claim("claude", "w") is None


def test_one_running_task_per_project(queue):
    queue.set_concurrency("media", 3)
    queue.enqueue("p1", "voice", "media", "k1")
    queue.enqueue("p1", "edit", "media", "k2")
    assert queue.claim("media", "w").phase == "voice"
    assert queue.claim("media", "w") is None


def test_paused_lane_does_not_dispatch_and_media_continues(queue):
    queue.enqueue("p1", "script", "claude", "k1")
    queue.enqueue("p2", "voice", "media", "k2")
    queue.pause_lane("claude", "Límite de uso")
    assert queue.claim("claude", "w") is None
    assert queue.claim("media", "w") is not None  # lo local sigue trabajando
    queue.resume_lane("claude")
    assert queue.claim("claude", "w") is not None


def test_lane_auto_resumes_at_reset_time(queue, clock):
    queue.enqueue("p1", "script", "claude", "k1")
    queue.pause_lane("claude", "Límite", resume_at=clock.t + 300)
    assert queue.claim("claude", "w") is None
    clock.t += 301
    assert queue.claim("claude", "w") is not None
    assert not queue.lanes()["claude"].paused


def test_expired_lease_is_requeued_then_fails_after_max_attempts(queue, clock):
    queue.enqueue("p1", "voice", "media", "k1", max_attempts=2)
    t = queue.claim("media", "w1")
    clock.t += 61
    assert [x.id for x in queue.requeue_expired()] == [t.id]
    t2 = queue.claim("media", "w2")
    assert t2.id == t.id and t2.attempts == 2
    clock.t += 61
    queue.requeue_expired()
    assert queue.tasks()[0].status == "failed"


def test_heartbeat_extends_lease(queue, clock):
    queue.enqueue("p1", "voice", "media", "k1")
    t = queue.claim("media", "w1")
    clock.t += 50
    assert queue.heartbeat(t.id, "w1")
    clock.t += 50
    assert queue.requeue_expired() == []


def test_delayed_task_waits(queue, clock):
    queue.enqueue("p1", "voice", "media", "k1", delay_s=30)
    assert queue.claim("media", "w") is None
    clock.t += 31
    assert queue.claim("media", "w") is not None


def test_concurrent_claims_never_duplicate(tmp_path):
    q = TaskQueue(make_engine(tmp_path / "c.db"), concurrency={"media": 50})
    for i in range(30):
        q.enqueue(f"p{i}", "voice", "media", f"k{i}")
    got, lock = [], threading.Lock()

    def grab():
        while (t := q.claim("media", threading.current_thread().name)) is not None:
            with lock:
                got.append(t.id)

    threads = [threading.Thread(target=grab) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(got) == sorted(set(got)) and len(got) == 30


def test_cancel_project_removes_queued(queue):
    queue.enqueue("p1", "a", "media", "k1")
    queue.enqueue("p2", "a", "media", "k2")
    assert queue.cancel_project("p1") == 1
    assert queue.claim("media", "w").project_id == "p2"


def test_one_active_task_per_project_phase_but_requeue_after_done(queue):
    a = queue.enqueue("p1", "script", "claude")
    assert queue.enqueue("p1", "script", "claude") == a
    t = queue.claim("claude", "w")
    queue.complete(t.id, "paused")
    b = queue.enqueue("p1", "script", "claude")  # tras terminar, se puede volver a encolar
    assert b != a
