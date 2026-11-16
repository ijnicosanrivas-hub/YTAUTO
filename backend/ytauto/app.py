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
from .providers.bootstrap import ProviderSystem, build_provider_system
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
    provider_system: ProviderSystem | None = None


def build_llm(settings: Settings, models: ModelConfig) -> LLMProvider:
    if settings.llm_provider == "local_draft":
        return LocalDraftLLM()
    return ClaudeCodeCLIProvider(claude_bin=settings.claude_bin, workdir=REPO_ROOT,
                                 timeout_s=settings.claude_timeout_s or models.timeout_s)


def build_app(settings: Settings, providers: ProviderGateway | None = None, llm: LLMProvider | None = None,
              models: ModelConfig | None = None, orchestrator_settings: OrchestratorSettings | None = None,
              include_mock_providers: bool = False) -> App:
    """Si no se pasa `providers`, se usa el Provider Registry persistido en la base de datos."""
    settings.ensure_dirs()
    models = models or ModelConfig.load()
    engine = make_engine(settings.db_path)
    store = SqlStateStore(engine)
    concurrency = min(settings.claude_concurrency or models.concurrency, models.max_concurrency)
    queue = TaskQueue(engine, concurrency={"claude": concurrency}, max_claude_concurrency=models.max_concurrency)
    events = EventBus()
    events.subscribe(lambda e: None if e.type in _EPHEMERAL_EVENTS else store.log_event(e))
    llm = llm or build_llm(settings, models)
    holder: dict[str, Orchestrator] = {}
    system = None
    if providers is None:
        def project_budget(pid: str) -> float | None:
            return store.get_project(pid).spec.budget_max_eur

        def preferred(pid: str | None) -> dict[str, str]:
            return store.get_project(pid).spec.preferred_providers if pid else {}

        system = build_provider_system(
            engine, settings.data_dir, settings.master_key, events=events, include_mocks=include_mock_providers,
            project_budget=project_budget, preferred=preferred,
            is_spend_authorized=lambda pid, prov: bool(holder) and holder["o"].is_spend_authorized(pid, prov))
        providers = system.gateway
        models.apply_overrides(system.budget.get_setting("model_overrides"))  # cambios hechos desde el panel
    orch = Orchestrator(store=store, llm=llm, providers=providers,
                        settings=orchestrator_settings or OrchestratorSettings(
                            projects_dir=settings.projects_dir, fix_major_when_passed=settings.fix_major_issues),
                        events=events, models=models,
                        cost_reader=(lambda pid: system.budget.ledger(pid)) if system else None)
    holder["o"] = orch
    worker = ProductionWorker(orch, queue)
    return App(settings=settings, store=store, queue=queue, events=events, llm=llm, providers=providers,
               orchestrator=orch, worker=worker, models=models, provider_system=system)
