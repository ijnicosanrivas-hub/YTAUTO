"""Bus de eventos en proceso. La API lo reenvía por WebSocket (actividad real)."""
from __future__ import annotations

import threading
from collections import deque
from typing import Any, Callable

from pydantic import BaseModel, Field

from .models import utcnow


class Event(BaseModel):
    type: str  # phase.status, agent.started, agent.progress, agent.finished, llm.call, cost, ...
    project_id: str | None = None
    agent: str | None = None
    phase: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    at: str = Field(default_factory=lambda: utcnow().isoformat())


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self, history: int = 1000):
        self._subs: list[Subscriber] = []
        self._lock = threading.Lock()
        self.history: deque[Event] = deque(maxlen=history)

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)

        return unsubscribe

    def publish(self, event: Event) -> None:
        self.history.append(event)
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(event)
            except Exception:  # un suscriptor roto no debe parar la producción
                pass

    def emit(self, type: str, **kwargs: Any) -> None:
        data = kwargs.pop("data", {}) or {}
        self.publish(Event(type=type, data=data, **kwargs))
