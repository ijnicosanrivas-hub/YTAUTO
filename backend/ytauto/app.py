"""Composición de la aplicación: une persistencia, cola, motor LLM, proveedores y orquestador."""
from __future__ import annotations

from dataclasses import dataclass

from .agents.base import ModelConfig
from .core.events import EventBus
from .core.settings import REPO_ROOT, Settings
from .db.schema import make_engine
from .db.store import SqlStateStore
from .llm.base import LLMProvider
from .llm.claude_cli import ClaudeCodeCLIProvider
from .llm.mock import LocalDraftLLM
from .orchestrator.orchestrator import Orchestrator, OrchestratorSettings
from .providers.interfaces import ProviderGateway
from .queue.task_queue import TaskQueue
from .queue.worker import ProductionWorker

# Eventos de alta frecuencia que no se guardan en el historial persistente.
_EPHEMERAL_EVENTS = {"agent.progress"}


@dataclass
class App:
    settings: Settings
    store: SqlStateStore
    queue: TaskQueue
    events: EventBus
    llm: LLMProvider
    providers: ProviderGateway
    orchestrator: Orchestrator
    worker: ProductionWorker
    models: ModelConfig


def build_llm(settings: Settings, models: ModelConfig) -> LLMProvider:
    if settings.llm_provider == "local_draft":
        return LocalDraftLLM()
    return ClaudeCodeCLIProvider(claude_bin=settings.claude_bin, workdir=REPO_ROOT,
                                 timeout_s=settings.claude_timeout_s or models.timeout_s)


def build_app(settings: Settings, providers: ProviderGateway, llm: LLMProvider | None = None,
              models: ModelConfig | None = None, orchestrator_settings: OrchestratorSettings | None = None) -> App:
    settings.ensure_dirs()
    models = models or ModelConfig.load()
    engine = make_engine(settings.db_path)
    store = SqlStateStore(engine)
    concurrency = min(settings.claude_concurrency or models.concurrency, models.max_concurrency)
    queue = TaskQueue(engine, concurrency={"claude": concurrency}, max_claude_concurrency=models.max_concurrency)
    events = EventBus()
    events.subscribe(lambda e: None if e.type in _EPHEMERAL_EVENTS else store.log_event(e))
    llm = llm or build_llm(settings, models)
    orch = Orchestrator(store=store, llm=llm, providers=providers,
                        settings=orchestrator_settings or OrchestratorSettings(projects_dir=settings.projects_dir),
                        events=events, models=models)
    worker = ProductionWorker(orch, queue)
    return App(settings=settings, store=store, queue=queue, events=events, llm=llm, providers=providers,
               orchestrator=orch, worker=worker, models=models)
