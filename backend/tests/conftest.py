from __future__ import annotations

from pathlib import Path

import pytest

from ytauto.agents.base import AgentContext, ModelConfig
from ytauto.core.events import EventBus
from ytauto.core.models import ProjectSpec
from ytauto.core.narrative import NarrativeTemplate
from ytauto.core.workspace import ProjectMemory, Workspace
from ytauto.llm.mock import LocalDraftLLM
from ytauto.orchestrator.orchestrator import Orchestrator, OrchestratorSettings
from ytauto.orchestrator.state import InMemoryStateStore
from ytauto.providers import mock as m
from ytauto.providers.gateway import DirectGateway
from ytauto.providers.interfaces import ProviderCategory as C
from ytauto.providers.subtitle.proportional import ProportionalSubtitleProvider


@pytest.fixture
def spec() -> ProjectSpec:
    return ProjectSpec(name="Prueba", topic="los pulpos", idea="curiosidades sobre pulpos", duration_s=60)


@pytest.fixture
def mock_providers():
    return {
        C.IMAGE: m.MockImageProvider(), C.TTS: m.MockTTSProvider(), C.MUSIC: m.MockMusicProvider(),
        C.SFX: m.MockSFXProvider(), C.SUBTITLE: ProportionalSubtitleProvider(),
        C.RENDERING: m.MockRenderingProvider(), C.STORAGE: m.MockStorageProvider(),
        C.PUBLISHING: m.MockPublishingProvider(),
    }


@pytest.fixture
def gateway(mock_providers):
    return DirectGateway(mock_providers)


@pytest.fixture
def make_ctx(tmp_path: Path, gateway, spec):
    def _make(llm=None, spec_override=None, **kw) -> AgentContext:
        ws = Workspace(tmp_path / "projects", "prj_test")
        return AgentContext(
            project_id="prj_test", spec=spec_override or spec, workspace=ws, memory=ProjectMemory(ws),
            llm=llm or LocalDraftLLM(), providers=kw.pop("providers", gateway), models=ModelConfig(),
            narrative=NarrativeTemplate.load(), events=EventBus(), **kw,
        )
    return _make


@pytest.fixture(params=["memory", "sqlite"])
def store_factory(request, tmp_path: Path):
    """Las pruebas del orquestador se ejecutan con ambos almacenes."""
    def _make():
        if request.param == "memory":
            return InMemoryStateStore()
        from ytauto.db.schema import make_engine
        from ytauto.db.store import SqlStateStore
        return SqlStateStore(make_engine(tmp_path / "ytauto.db"))
    return _make


@pytest.fixture
def make_orchestrator(tmp_path: Path, gateway, store_factory):
    def _make(llm=None, store=None, providers=None, **settings) -> Orchestrator:
        return Orchestrator(
            store=store or store_factory(), llm=llm or LocalDraftLLM(), providers=providers or gateway,
            settings=OrchestratorSettings(projects_dir=tmp_path / "projects", **settings),
        )
    return _make
