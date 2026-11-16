"""Puerto de persistencia del orquestador.

`StateStore` es la interfaz; `InMemoryStateStore` sirve para pruebas y la implementación
SQLite (fase 3) vive en `ytauto.db.store`.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from ..core.models import CorrectionRequest, PhaseStatus, ProjectSpec, ProjectStatus, utcnow
from .pipeline import PIPELINE


class PhaseRecord(BaseModel):
    project_id: str
    phase: str
    status: PhaseStatus = PhaseStatus.PENDING
    attempts: int = 0
    error: str | None = None
    blocked_code: str | None = None
    retryable: bool = False  # error transitorio: la cola puede reintentar con espera
    summary: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    scene_filter: list[int] | None = None
    corrections: list[CorrectionRequest] = Field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None


class ProjectRecord(BaseModel):
    id: str
    spec: ProjectSpec
    status: ProjectStatus = ProjectStatus.ACTIVE
    correction_rounds: int = 0
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: utcnow().isoformat())
    blocked_reason: str | None = None


class Approval(BaseModel):
    project_id: str
    gate: str  # script_approval | final_approval | publish:<platform> | spend:<provider>
    approved: bool
    by: str = "user"
    note: str = ""
    at: str = Field(default_factory=lambda: utcnow().isoformat())
    expires_at: str | None = None
    id: str = ""


class StateStore(ABC):
    @abstractmethod
    def create_project(self, record: ProjectRecord) -> None: ...
    @abstractmethod
    def get_project(self, project_id: str) -> ProjectRecord: ...
    @abstractmethod
    def save_project(self, record: ProjectRecord) -> None: ...
    @abstractmethod
    def list_projects(self) -> list[ProjectRecord]: ...
    @abstractmethod
    def get_phase(self, project_id: str, phase: str) -> PhaseRecord: ...
    @abstractmethod
    def save_phase(self, record: PhaseRecord) -> None: ...
    @abstractmethod
    def list_phases(self, project_id: str) -> list[PhaseRecord]: ...
    @abstractmethod
    def add_approval(self, approval: Approval) -> Approval: ...
    @abstractmethod
    def get_approvals(self, project_id: str) -> list[Approval]: ...
    @abstractmethod
    def record_llm_usage(self, project_id: str, agent: str, phase: str, usage: dict[str, Any]) -> None: ...
    @abstractmethod
    def llm_usage(self, project_id: str | None = None) -> list[dict[str, Any]]: ...


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.projects: dict[str, ProjectRecord] = {}
        self.phases: dict[tuple[str, str], PhaseRecord] = {}
        self.approvals: list[Approval] = []
        self.usage: list[dict[str, Any]] = []

    def create_project(self, record: ProjectRecord) -> None:
        with self._lock:
            if record.id in self.projects:
                raise ValueError(f"Proyecto duplicado: {record.id}")
            self.projects[record.id] = record
            for p in PIPELINE:
                self.phases[(record.id, p.id)] = PhaseRecord(project_id=record.id, phase=p.id)

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._lock:
            return self.projects[project_id].model_copy(deep=True)

    def save_project(self, record: ProjectRecord) -> None:
        with self._lock:
            record.updated_at = utcnow().isoformat()
            self.projects[record.id] = record.model_copy(deep=True)

    def list_projects(self) -> list[ProjectRecord]:
        with self._lock:
            return [p.model_copy(deep=True) for p in self.projects.values()]

    def get_phase(self, project_id: str, phase: str) -> PhaseRecord:
        with self._lock:
            return self.phases[(project_id, phase)].model_copy(deep=True)

    def save_phase(self, record: PhaseRecord) -> None:
        with self._lock:
            self.phases[(record.project_id, record.phase)] = record.model_copy(deep=True)

    def list_phases(self, project_id: str) -> list[PhaseRecord]:
        with self._lock:
            return [self.phases[(project_id, p.id)].model_copy(deep=True) for p in PIPELINE]

    def add_approval(self, approval: Approval) -> Approval:
        with self._lock:
            approval.id = approval.id or f"apr_{len(self.approvals) + 1}"
            self.approvals.append(approval)
            return approval

    def get_approvals(self, project_id: str) -> list[Approval]:
        with self._lock:
            return [a for a in self.approvals if a.project_id == project_id]

    def record_llm_usage(self, project_id: str, agent: str, phase: str, usage: dict[str, Any]) -> None:
        with self._lock:
            self.usage.append({"project_id": project_id, "agent": agent, "phase": phase,
                               "at": utcnow().isoformat(), **usage})

    def llm_usage(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [u for u in self.usage if project_id is None or u["project_id"] == project_id]
