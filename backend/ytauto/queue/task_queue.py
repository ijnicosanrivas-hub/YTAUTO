"""Cola centralizada de tareas sobre SQLite.

- Carriles (`lane`): `claude` (consume la suscripción), `media` (FFmpeg/TTS local) y `none`
  (pasos instantáneos: aprobaciones, informe). Cada carril tiene su concurrencia.
- Por defecto el carril `claude` tiene concurrencia 1; nunca se supera `max_claude_concurrency`.
- Idempotencia: `idempotency_key` única → encolar dos veces la misma ejecución no duplica.
- Un proyecto nunca tiene dos tareas en ejecución a la vez (sus fases son secuenciales).
- Leases con caducidad: si un worker muere, la tarea vuelve a la cola al caducar el lease.
- Pausa por carril (p. ej. límite de uso de Claude) con reanudación manual o programada.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ..core.models import utcnow
from ..db import schema as s

LANES = ("claude", "media", "none")
DEFAULT_CONCURRENCY = {"claude": 1, "media": 1, "none": 4}


class Task(BaseModel):
    id: int
    project_id: str
    phase: str
    lane: str
    status: str
    idempotency_key: str
    attempts: int
    max_attempts: int
    next_run_at: float
    lease_owner: str | None = None
    lease_until: float | None = None
    outcome: str | None = None
    error: str | None = None


class LaneState(BaseModel):
    lane: str
    paused: bool
    reason: str | None = None
    resume_at: float | None = None
    concurrency: int


class TaskQueue:
    def __init__(self, engine: Engine, concurrency: dict[str, int] | None = None, max_claude_concurrency: int = 2,
                 lease_s: float = 1800, clock: Callable[[], float] = time.time):
        self.engine = engine
        self.clock = clock
        self.lease_s = lease_s
        self.max_claude_concurrency = max_claude_concurrency
        self._claim_lock = threading.Lock()
        s.init_db(engine)
        wanted = {**DEFAULT_CONCURRENCY, **(concurrency or {})}
        with engine.begin() as c:
            for lane in LANES:
                exists = c.execute(select(s.queue_control.c.lane).where(s.queue_control.c.lane == lane)).first()
                if not exists:
                    c.execute(insert(s.queue_control).values(lane=lane, paused=False,
                                                             concurrency=self._clamp(lane, wanted[lane])))
        if concurrency:
            for lane, n in concurrency.items():
                self.set_concurrency(lane, n)

    def _clamp(self, lane: str, n: int) -> int:
        n = max(1, int(n))
        return min(n, self.max_claude_concurrency) if lane == "claude" else n

    # ------------------------------------------------------------------ encolar
    def enqueue(self, project_id: str, phase: str, lane: str, key: str | None = None, max_attempts: int = 3,
                delay_s: float = 0.0) -> int | None:
        """Encola una ejecución. Idempotente en dos niveles:
        - misma `key` → devuelve la tarea existente (reintentos de la API, dobles clics);
        - ya hay una tarea activa para (proyecto, fase) → devuelve esa.
        """
        if lane not in LANES:
            raise ValueError(f"Carril desconocido: {lane}")
        key = key or f"{project_id}:{phase}:{uuid.uuid4().hex[:12]}"
        now = utcnow().isoformat()
        active = self._active(project_id, phase)
        if active is not None:
            return active
        try:
            with self.engine.begin() as c:
                res = c.execute(insert(s.tasks).values(
                    project_id=project_id, phase=phase, lane=lane, status="queued", idempotency_key=key,
                    attempts=0, max_attempts=max_attempts, next_run_at=self.clock() + delay_s,
                    created_at=now, updated_at=now))
                return int(res.inserted_primary_key[0])
        except IntegrityError:
            with self.engine.connect() as c:
                row = c.execute(select(s.tasks.c.id).where(s.tasks.c.idempotency_key == key)).first()
            if row:
                return int(row[0])
            return self._active(project_id, phase)

    def _active(self, project_id: str, phase: str) -> int | None:
        with self.engine.connect() as c:
            row = c.execute(select(s.tasks.c.id).where(
                s.tasks.c.project_id == project_id, s.tasks.c.phase == phase,
                s.tasks.c.status.in_(("queued", "leased")))).first()
        return int(row[0]) if row else None

    # ------------------------------------------------------------------ reclamar
    def claim(self, lane: str, owner: str) -> Task | None:
        now = self.clock()
        with self._claim_lock, self.engine.begin() as c:
            ctl = c.execute(select(s.queue_control).where(s.queue_control.c.lane == lane)).mappings().first()
            if ctl["paused"]:
                if ctl["resume_at"] is not None and ctl["resume_at"] <= now:
                    c.execute(update(s.queue_control).where(s.queue_control.c.lane == lane)
                              .values(paused=False, reason=None, resume_at=None))
                else:
                    return None
            running = c.execute(select(func.count()).select_from(s.tasks).where(
                s.tasks.c.lane == lane, s.tasks.c.status == "leased")).scalar_one()
            if running >= ctl["concurrency"]:
                return None
            busy_projects = select(s.tasks.c.project_id).where(s.tasks.c.status == "leased")
            row = c.execute(
                select(s.tasks).where(
                    s.tasks.c.lane == lane, s.tasks.c.status == "queued", s.tasks.c.next_run_at <= now,
                    s.tasks.c.project_id.not_in(busy_projects),
                ).order_by(s.tasks.c.next_run_at, s.tasks.c.id).limit(1)
            ).mappings().first()
            if row is None:
                return None
            res = c.execute(update(s.tasks).where(s.tasks.c.id == row["id"], s.tasks.c.status == "queued").values(
                status="leased", lease_owner=owner, lease_until=now + self.lease_s, attempts=row["attempts"] + 1,
                updated_at=utcnow().isoformat()))
            if res.rowcount != 1:
                return None  # otro proceso la reclamó antes
            data = dict(row) | {"status": "leased", "lease_owner": owner, "lease_until": now + self.lease_s,
                                "attempts": row["attempts"] + 1}
        return Task(**{k: data[k] for k in Task.model_fields})

    def heartbeat(self, task_id: int, owner: str) -> bool:
        with self.engine.begin() as c:
            res = c.execute(update(s.tasks).where(s.tasks.c.id == task_id, s.tasks.c.lease_owner == owner,
                                                  s.tasks.c.status == "leased")
                            .values(lease_until=self.clock() + self.lease_s))
            return res.rowcount == 1

    def complete(self, task_id: int, outcome: str, error: str | None = None, failed: bool = False) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.tasks).where(s.tasks.c.id == task_id).values(
                status="failed" if failed else "done", outcome=outcome, error=error, lease_owner=None,
                lease_until=None, updated_at=utcnow().isoformat()))

    def cancel_project(self, project_id: str) -> int:
        with self.engine.begin() as c:
            return c.execute(update(s.tasks).where(s.tasks.c.project_id == project_id,
                                                   s.tasks.c.status == "queued").values(status="cancelled")).rowcount

    def requeue_expired(self) -> list[Task]:
        """Leases caducados (worker caído) → vuelven a 'queued' o a 'failed' si agotaron intentos."""
        now = self.clock()
        with self.engine.begin() as c:
            rows = c.execute(select(s.tasks).where(s.tasks.c.status == "leased",
                                                   s.tasks.c.lease_until < now)).mappings().all()
            for r in rows:
                exhausted = r["attempts"] >= r["max_attempts"]
                c.execute(update(s.tasks).where(s.tasks.c.id == r["id"]).values(
                    status="failed" if exhausted else "queued", lease_owner=None, lease_until=None,
                    error="Lease caducado (worker interrumpido)", updated_at=utcnow().isoformat()))
        return [Task(**{k: r[k] for k in Task.model_fields}) for r in rows]

    # ------------------------------------------------------------------ control de carriles
    def pause_lane(self, lane: str, reason: str, resume_at: float | None = None) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.queue_control).where(s.queue_control.c.lane == lane)
                      .values(paused=True, reason=reason, resume_at=resume_at))

    def resume_lane(self, lane: str) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.queue_control).where(s.queue_control.c.lane == lane)
                      .values(paused=False, reason=None, resume_at=None))

    def set_concurrency(self, lane: str, n: int) -> int:
        n = self._clamp(lane, n)
        with self.engine.begin() as c:
            c.execute(update(s.queue_control).where(s.queue_control.c.lane == lane).values(concurrency=n))
        return n

    def lanes(self) -> dict[str, LaneState]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.queue_control)).mappings().all()
        return {r["lane"]: LaneState(**dict(r)) for r in rows}

    # ------------------------------------------------------------------ consultas
    def tasks(self, project_id: str | None = None, status: str | None = None) -> list[Task]:
        conds = []
        if project_id:
            conds.append(s.tasks.c.project_id == project_id)
        if status:
            conds.append(s.tasks.c.status == status)
        q = select(s.tasks)
        if conds:
            q = q.where(and_(*conds))
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.tasks.c.id)).mappings().all()
        return [Task(**{k: r[k] for k in Task.model_fields}) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.tasks.c.lane, s.tasks.c.status, func.count())
                             .group_by(s.tasks.c.lane, s.tasks.c.status)).all()
        out: dict[str, dict[str, int]] = {lane: {} for lane in LANES}
        for lane, status, n in rows:
            out.setdefault(lane, {})[status] = n
        return out
