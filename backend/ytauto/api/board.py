"""Estado en vivo de los nueve agentes, derivado SOLO de eventos reales del sistema.

No hay animación inventada: un nodo está "running" únicamente si el orquestador emitió
`agent.started` y aún no `agent.finished`/error. Se reconstruye desde el registro de
eventos persistido al arrancar.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel

from ..agents.registry import AGENT_CLASSES
from ..core.events import Event
from ..orchestrator.pipeline import PIPELINE


class AgentState(BaseModel):
    name: str
    channel: str | None = None
    title: str
    uses_claude: bool
    phases: list[str]
    status: str = "idle"  # idle | running | waiting | error
    project_id: str | None = None
    phase: str | None = None
    task: str | None = None
    progress: float | None = None
    started_at: str | None = None
    finished_at: str | None = None
    last_duration_s: float | None = None
    last_result: str | None = None
    last_error: str | None = None
    runs: int = 0
    errors: int = 0
    llm_calls: int = 0


class Link(BaseModel):
    source: str
    target: str
    kind: str  # control (jefe→agente) | flow (entrega entre agentes)


class Board:
    def __init__(self, channel: str | None = None) -> None:
        self._lock = threading.Lock()
        self.channel = channel
        self.agents: dict[str, AgentState] = {
            cls.name: AgentState(name=cls.name, channel=channel, title=cls.title, uses_claude=cls.uses_claude,
                                 phases=sorted(cls.phases, key=[p.id for p in PIPELINE].index))
            for cls in AGENT_CLASSES
        }
        self.phase_agent = {p.id: p.agent for p in PIPELINE}

    @staticmethod
    def links() -> list[Link]:
        out = [Link(source="chief", target=c.name, kind="control") for c in AGENT_CLASSES if c.name != "chief"]
        seen = set()
        for p in PIPELINE:  # entregas reales entre agentes según las dependencias del flujo
            for dep in p.depends_on:
                a, b = next(x.agent for x in PIPELINE if x.id == dep), p.agent
                if a and b and a != b and (a, b) not in seen and "chief" not in (a, b):
                    seen.add((a, b))
                    out.append(Link(source=a, target=b, kind="flow"))
        return out

    def apply(self, e: Event) -> AgentState | None:
        name = e.agent or (self.phase_agent.get(e.phase) if e.phase else None)
        if not name or name not in self.agents:
            return None
        with self._lock:
            a = self.agents[name]
            if e.type == "agent.started":
                a.status, a.project_id, a.phase = "running", e.project_id, e.phase
                a.task, a.progress, a.started_at, a.finished_at = f"Fase {e.phase}", 0.0, e.at, None
                a.runs += 1
            elif e.type == "agent.progress" and a.status == "running":
                a.progress = e.data.get("progress")
                if e.data.get("message"):
                    a.task = e.data["message"]
            elif e.type == "agent.finished":
                a.status = "waiting" if e.data.get("status") == "in_review" else "idle"
                a.progress, a.finished_at = 1.0, e.at
                a.last_result = e.data.get("summary")
                a.last_duration_s = _elapsed(a.started_at, e.at)
            elif e.type == "llm.call":
                a.llm_calls += 1
                a.task = f"Consultando a Claude ({e.data.get('model')}, intento {e.data.get('attempt')})"
            elif e.type == "phase.status":
                st = e.data.get("status")
                if st == "error":
                    a.status, a.errors, a.last_error = "error", a.errors + 1, e.data.get("error")
                    a.finished_at = e.at
                elif st == "blocked":
                    a.status, a.last_error = "waiting", e.data.get("error")
            return a.model_copy()

    def snapshot(self) -> list[AgentState]:
        with self._lock:
            return [a.model_copy() for a in self.agents.values()]


def _elapsed(start: str | None, end: str) -> float | None:
    if not start:
        return None
    try:
        return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 2)
    except ValueError:
        return None


class ChannelBoards:
    """Un tablero por canal: los nueve agentes de cada canal trabajan en paralelo sin pisarse."""

    def __init__(self, channel_ids: list[str], channel_of: Callable[[str], str | None]):
        self.boards = {c: Board(c) for c in channel_ids}
        self.default = channel_ids[0]
        self._channel_of = channel_of
        self._cache: dict[str, str | None] = {}

    def board(self, channel: str | None) -> Board:
        return self.boards.get(channel or self.default) or self.boards[self.default]

    def channel_of(self, project_id: str | None) -> str | None:
        if not project_id:
            return None
        if project_id not in self._cache:
            ch = self._channel_of(project_id)
            self._cache[project_id] = ch if ch in self.boards else (self.default if ch else None)
        return self._cache[project_id]

    def apply(self, e: Event) -> AgentState | None:
        ch = self.channel_of(e.project_id)
        return self.boards[ch].apply(e) if ch else None

    def snapshot(self) -> dict[str, list[AgentState]]:
        return {c: b.snapshot() for c, b in self.boards.items()}


def rebuild(board: Board | ChannelBoards, events: list[dict[str, Any]]) -> None:
    for row in events:
        board.apply(Event(type=row["type"], project_id=row.get("project_id"), agent=row.get("agent"),
                          phase=row.get("phase"), data=row.get("data") or {}, at=row["at"]))
    # Tras un reinicio nada está realmente en ejecución
    for b in (board.boards.values() if isinstance(board, ChannelBoards) else [board]):
        for a in b.agents.values():
            if a.status == "running":
                a.status, a.task = "idle", "Interrumpido (reinicio)"
