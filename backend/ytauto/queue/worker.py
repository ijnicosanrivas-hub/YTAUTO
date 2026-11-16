"""Worker de producción: consume la cola y hace avanzar los proyectos fase a fase."""
from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor

from ..core.models import PhaseStatus, ProjectStatus
from ..orchestrator.orchestrator import Orchestrator
from .task_queue import LANES, Task, TaskQueue

log = logging.getLogger("ytauto.worker")

DEFAULT_BACKOFF_S = (30.0, 120.0, 600.0)


def parse_resume_at(resets_at: str | None) -> float | None:
    """Convierte la indicación de reinicio de Claude Code en epoch si es posible."""
    if resets_at and resets_at.strip().isdigit():
        return float(resets_at.strip())
    return None  # desconocido → reanudación manual (no se reintenta a ciegas)


class ProductionWorker:
    def __init__(self, orchestrator: Orchestrator, queue: TaskQueue, owner: str | None = None,
                 backoff_s: tuple[float, ...] = DEFAULT_BACKOFF_S, max_retries: int = 3):
        self.orch = orchestrator
        self.queue = queue
        # Identificador único por proceso: los leases distinguen qué proceso tiene cada tarea.
        self.owner = owner or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.backoff_s = backoff_s
        self.max_retries = max_retries
        self._stop = threading.Event()

    # ------------------------------------------------------------------ planificación
    def schedule(self, pid: str, delay_s: float = 0.0) -> int | None:
        """Encola la siguiente fase ejecutable del proyecto (idempotente)."""
        project = self.orch.store.get_project(pid)
        if project.status not in (ProjectStatus.ACTIVE,):
            return None
        phase = self.orch.next_phase(pid)
        if phase is None:
            return None
        rec = self.orch.store.get_phase(pid, phase.id)
        if rec.status not in (PhaseStatus.PENDING, PhaseStatus.IN_REVIEW, PhaseStatus.BLOCKED):
            return None
        if rec.status is PhaseStatus.BLOCKED and rec.blocked_code != "publish_authorization":
            return None
        # La cola garantiza como mucho una tarea activa por (proyecto, fase).
        return self.queue.enqueue(pid, phase.id, phase.queue, max_attempts=self.max_retries, delay_s=delay_s)

    def schedule_all(self) -> int:
        n = 0
        for p in self.orch.store.list_projects():
            if p.status is ProjectStatus.ACTIVE and self.schedule(p.id) is not None:
                n += 1
        return n

    # ------------------------------------------------------------------ recuperación
    def recover(self) -> None:
        """Al arrancar o en cada ciclo: leases caducados y fases que quedaron 'running'."""
        for task in self.queue.requeue_expired():
            self.orch.recover_interrupted(task.project_id)
            log.warning("Tarea %s (%s/%s) recuperada tras lease caducado", task.id, task.project_id, task.phase)
        self._auto_resume_claude()

    def recover_on_startup(self) -> None:
        """Tras un reinicio del proceso, ninguna fase puede estar realmente en ejecución."""
        for t in self.queue.tasks(status="leased"):
            self.queue.complete(t.id, "interrupted", "Proceso reiniciado", failed=False)
        for p in self.orch.store.list_projects():
            self.orch.recover_interrupted(p.id)
        self.schedule_all()

    def _auto_resume_claude(self) -> None:
        lane = self.queue.lanes()["claude"]
        if lane.paused:
            return
        # Carril activo de nuevo: se reanudan los proyectos bloqueados por límite de uso.
        for p in self.orch.store.list_projects():
            if p.status is ProjectStatus.BLOCKED:
                phases = self.orch.store.list_phases(p.id)
                if any(ph.blocked_code == "usage_limit" for ph in phases):
                    self.orch.resume(p.id)
                    self.schedule(p.id)

    def resume_claude(self) -> None:
        """Reanudación manual tras un límite de uso o tras `claude /login`."""
        self.queue.resume_lane("claude")
        for p in self.orch.store.list_projects():
            if p.status is ProjectStatus.BLOCKED and any(
                    ph.blocked_code in ("usage_limit", "auth") for ph in self.orch.store.list_phases(p.id)):
                self.orch.resume(p.id)
                self.schedule(p.id)

    # ------------------------------------------------------------------ ejecución
    def execute(self, task: Task) -> str:
        pid = task.project_id
        project = self.orch.store.get_project(pid)
        nxt = self.orch.next_phase(pid)
        if project.status is not ProjectStatus.ACTIVE or nxt is None or nxt.id != task.phase:
            self.queue.complete(task.id, "stale")
            return "stale"
        result = self.orch.step(pid)
        outcome = result.outcome
        if outcome == "ran":
            self.queue.complete(task.id, outcome)
            if self.orch.next_phase(pid) is None:
                self.orch.step(pid)  # marca el proyecto como completado
            else:
                self.schedule(pid)
        elif outcome == "usage_limit":
            resume_at = parse_resume_at(result.resets_at)
            self.queue.pause_lane("claude", f"Límite de uso de Claude: {result.message[:200]}", resume_at)
            self.queue.complete(task.id, outcome, result.message)
        elif outcome == "auth_error":
            self.queue.pause_lane("claude", "Claude Code no autenticado: ejecuta `claude /login`", None)
            self.queue.complete(task.id, outcome, result.message)
        elif outcome == "error":
            rec = self.orch.store.get_phase(pid, task.phase)
            if rec.retryable and rec.attempts < self.max_retries:
                delay = self.backoff_s[min(rec.attempts - 1, len(self.backoff_s) - 1)]
                self.queue.complete(task.id, "retry_scheduled", result.message)
                self.orch.retry_phase(pid, task.phase)
                self.schedule(pid, delay_s=delay)
            else:
                self.queue.complete(task.id, outcome, result.message, failed=True)
        else:  # waiting_approval, blocked, paused, cancelled, completed, idle
            self.queue.complete(task.id, outcome, result.message or None)
        return outcome

    def tick(self) -> int:
        """Un ciclo síncrono: reclama y ejecuta como mucho una tarea por carril. Devuelve nº ejecutadas."""
        self.recover()
        done = 0
        for lane in LANES:
            task = self.queue.claim(lane, self.owner)
            if task:
                self._safe_execute(task)
                done += 1
        return done

    def run_until_idle(self, max_ticks: int = 500) -> int:
        total = 0
        for _ in range(max_ticks):
            n = self.tick()
            total += n
            if n == 0:
                break
        return total

    def _safe_execute(self, task: Task) -> None:
        # Latido: renueva el lease mientras la tarea trabaja (FFmpeg puede tardar minutos).
        done = threading.Event()
        interval = max(0.05, self.queue.lease_s / 4)

        def beat() -> None:
            while not done.wait(interval):
                self.queue.heartbeat(task.id, self.owner)

        hb = threading.Thread(target=beat, name=f"lease-{task.id}", daemon=True)
        hb.start()
        try:
            self.execute(task)
        except Exception as e:  # noqa: BLE001 - el worker no debe morir por una tarea
            log.exception("Fallo del worker en la tarea %s", task.id)
            self.queue.complete(task.id, "worker_error", str(e), failed=True)
        finally:
            done.set()

    # ------------------------------------------------------------------ bucle en segundo plano
    def run_forever(self, poll_s: float = 1.0) -> None:
        """Bucle con hilos: respeta la concurrencia de cada carril (claude=1 por defecto)."""
        lanes = self.queue.lanes()
        workers = sum(lanes[lane].concurrency for lane in LANES)
        self.recover_on_startup()
        running: list[Future] = []
        with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="ytauto") as pool:
            while not self._stop.is_set():
                self.recover()
                running = [f for f in running if not f.done()]
                claimed = False
                for lane in LANES:
                    if self._stop.is_set():
                        break  # apagando: no se reservan tareas nuevas
                    task = self.queue.claim(lane, self.owner)
                    if task:
                        running.append(pool.submit(self._safe_execute, task))
                        claimed = True
                if not claimed:
                    self._stop.wait(poll_s)
            # Al salir del bloque `with`, el pool espera a que terminen las tareas en curso.

    def stop(self) -> None:
        self._stop.set()
