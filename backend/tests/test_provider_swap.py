"""Demostración obligatoria: sustituir, añadir y quitar proveedores sin tocar agentes ni orquestador.

También: fallback, prohibición de saltar a un proveedor de pago sin autorización, presupuesto.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from ytauto.core.errors import BudgetExceeded, ProviderError, SpendNotAuthorized
from ytauto.core.events import EventBus
from ytauto.core.models import AssetKind, License, MediaAsset, PhaseStatus, ProjectSpec, ProjectStatus
from ytauto.db.schema import make_engine
from ytauto.db.store import SqlStateStore
from ytauto.llm.mock import LocalDraftLLM
from ytauto.orchestrator.orchestrator import Orchestrator, OrchestratorSettings
from ytauto.providers.interfaces import ImageRequest, ProviderCategory as C, TextToSpeechProvider, TTSRequest, Voice
from ytauto.providers.mock import write_tone
from ytauto.providers.registry import (
    BudgetManager, CredentialVault, ProviderRegistry, RegistryGateway, register_adapter, unregister_adapter,
)


# Un adaptador "nuevo" que llega después (como si se instalara un nuevo motor de voz).
class AcmeVoiceProvider(TextToSpeechProvider):
    """Motor de voz de ejemplo añadido sin modificar el sistema."""
    name = "acme_voice"
    display_name = "ACME Voice"

    def list_voices(self, language=None):
        return [Voice(id="acme-es", name="Acme ES", language="es")]

    def synthesize(self, request: TTSRequest) -> MediaAsset:
        dur = max(0.5, len(request.text.split()) / 2.6)
        write_tone(request.out_path, dur, freq=300)
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(request.out_path), duration_s=round(dur, 3),
                          provider=self.name, license=License(name="generated", commercial_use=True))


@pytest.fixture
def acme():
    register_adapter(AcmeVoiceProvider)
    yield
    unregister_adapter("acme_voice")


@pytest.fixture
def system(tmp_path):
    engine = make_engine(tmp_path / "y.db")
    store = SqlStateStore(engine)
    registry = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()), include_mocks=True)
    for adapter in ("mock_image", "mock_tts", "mock_music", "mock_sfx", "proportional", "mock_render",
                    "mock_publisher"):
        registry.add(adapter)
    events = EventBus()
    holder = {}
    budget = BudgetManager(engine, project_budget=lambda pid: store.get_project(pid).spec.budget_max_eur,
                           on_warning=lambda m, d: events.emit("budget.warning", data={"message": m}))
    gateway = RegistryGateway(registry, budget,
                              is_spend_authorized=lambda pid, prov: holder["o"].is_spend_authorized(pid, prov),
                              preferred=lambda pid: store.get_project(pid).spec.preferred_providers if pid else {},
                              events=events)
    orch = Orchestrator(store=store, llm=LocalDraftLLM(), providers=gateway, events=events,
                        settings=OrchestratorSettings(projects_dir=tmp_path / "projects"),
                        cost_reader=budget.ledger)
    holder["o"] = orch
    return orch, registry, budget, gateway, events


def produce(orch, **spec_kw):
    spec = ProjectSpec(**{"name": "swap", "topic": "los glaciares", "duration_s": 50,
                          "require_script_approval": False, **spec_kw})
    pid = orch.create_project(spec)
    return pid, orch.run(pid)


def voice_providers(orch, pid):
    from ytauto.core.workspace import Workspace
    ws = Workspace(orch.settings.projects_dir, pid)
    vm = ws.load("voice", "voice_manifest")
    return vm["voice_id"]


def test_swap_voice_provider_without_touching_agents(system, acme):
    orch, registry, *_ = system
    pid1, r1 = produce(orch)
    assert r1.phase == "final_approval"
    assert voice_providers(orch, pid1) == "mock-es-1"
    # 1) instalar adaptador (acme) 2) configurarlo 3) probarlo 4) seleccionarlo
    registry.add("acme_voice")
    assert registry.test("acme_voice").passed
    registry.set_primary(C.TTS, "acme_voice")
    pid2, r2 = produce(orch)
    assert r2.phase == "final_approval"
    assert voice_providers(orch, pid2) == "acme-es"
    # Mismo código de agentes y orquestador en ambas producciones (verificado por test_architecture).


def test_swap_every_category_by_registry_only(system):
    orch, registry, *_ = system
    for adapter, cat in (("mock_image", C.IMAGE), ("mock_music", C.MUSIC), ("mock_sfx", C.SFX)):
        registry.add(adapter, id=f"{adapter}_2")
        registry.set_primary(cat, f"{adapter}_2")
    pid, r = produce(orch)
    assert r.phase == "final_approval"
    from ytauto.core.workspace import Workspace
    assets = Workspace(orch.settings.projects_dir, pid).load("resources", "assets")
    assert {a["metadata"]["provider_instance"] for a in assets.values()} == {"mock_image_2"}


def test_remove_provider_and_project_still_runs(system):
    orch, registry, *_ = system
    registry.add("mock_image", id="img_extra")
    registry.remove("mock_image")
    pid, r = produce(orch)
    assert r.phase == "final_approval"


def test_fallback_when_primary_fails(system):
    orch, registry, _, _, events = system
    seen = []
    events.subscribe(lambda e: seen.append(e) if e.type == "provider.fallback" else None)
    registry.add("failing_image")
    registry.set_primary(C.IMAGE, "failing_image")
    pid, r = produce(orch)
    assert r.phase == "final_approval"
    assert seen and seen[0].data["used"] == "mock_image"
    assert registry.status("failing_image").error_count > 0


def test_never_falls_back_to_paid_provider_without_authorization(system, tmp_path):
    orch, registry, budget, gateway, _ = system
    registry.add("mock_paid_image", credentials={"api_key": "key-1234567890"})
    registry.add("failing_image")
    registry.remove("mock_image")
    registry.set_order(C.IMAGE, ["failing_image", "mock_paid_image"])
    with pytest.raises(ProviderError) as e:
        gateway.invoke(C.IMAGE, "generate", ImageRequest(prompt="x", out_dir=tmp_path), project_id=None)
    assert "sin autorización" in str(e.value)
    assert budget.ledger() == []  # ningún gasto


def test_paid_primary_blocks_phase_until_user_authorizes(system):
    orch, registry, budget, *_ = system
    registry.add("mock_paid_image", credentials={"api_key": "key-1234567890"})
    registry.set_primary(C.IMAGE, "mock_paid_image")
    registry.disable("mock_image")
    pid, r = produce(orch, budget_max_eur=2.0)
    assert r.outcome == "blocked" and r.phase == "resource_generation"
    assert orch.store.get_phase(pid, "resource_generation").blocked_code == "spend_not_authorized"
    assert orch.store.get_project(pid).status is ProjectStatus.BLOCKED
    assert budget.ledger(pid) == []
    orch.approve(pid, "spend:mock_paid_image", note="OK hasta 2 €")
    r = orch.run(pid)
    assert r.phase == "final_approval"
    spent = budget.spent_project(pid)
    assert 0 < spent <= 2.0
    orch.approve(pid, "final_approval")
    orch.run(pid)
    orch.approve(pid, "publish_decision")
    orch.run(pid)
    from ytauto.core.workspace import Workspace
    report = Workspace(orch.settings.projects_dir, pid).load("reports", "report")
    assert report["external_costs_eur"] == pytest.approx(spent)


def test_budget_blocks_when_exceeded(system):
    orch, registry, budget, *_ = system
    registry.add("mock_paid_image", credentials={"api_key": "key-1234567890"})
    registry.set_primary(C.IMAGE, "mock_paid_image")
    registry.disable("mock_image")
    pid, _ = produce(orch, budget_max_eur=0.10)  # solo alcanza para 2 imágenes de 0,04 €
    orch.approve(pid, "spend:mock_paid_image")
    r = orch.run(pid)
    assert r.outcome == "blocked"
    rec = orch.store.get_phase(pid, "resource_generation")
    assert rec.blocked_code == "budget_exceeded" and "insuficiente" in rec.error
    assert budget.spent_project(pid) <= 0.10


def test_budget_warning_and_monthly_and_generation_limits(system, tmp_path):
    orch, registry, budget, gateway, events = system
    warnings = []
    events.subscribe(lambda e: warnings.append(e) if e.type == "budget.warning" else None)
    registry.add("mock_paid_image", credentials={"api_key": "key-1234567890"}, max_generations_per_project=3)
    registry.set_primary(C.IMAGE, "mock_paid_image")
    registry.disable("mock_image")
    pid = orch.create_project(ProjectSpec(name="b", topic="t", budget_max_eur=0.15))
    orch.approve(pid, "spend:mock_paid_image")
    req = ImageRequest(prompt="x", out_dir=tmp_path)
    for _ in range(3):
        gateway.invoke(C.IMAGE, "generate", req, project_id=pid)
    assert warnings  # 0,12 de 0,15 = 80 %
    with pytest.raises(BudgetExceeded):
        gateway.invoke(C.IMAGE, "generate", req, project_id=pid)  # 4ª generación o presupuesto
    budget.set_setting("monthly_budget_eur", 0.10)
    pid2 = orch.create_project(ProjectSpec(name="c", topic="t", budget_max_eur=5))
    orch.approve(pid2, "spend:mock_paid_image")
    with pytest.raises(BudgetExceeded) as e:
        gateway.invoke(C.IMAGE, "generate", req, project_id=pid2)
    assert "mensual" in str(e.value)


def test_project_preferred_provider_is_used_first(system, acme):
    orch, registry, *_ = system
    registry.add("acme_voice")  # alternativo, no principal
    pid, r = produce(orch, preferred_providers={"tts": "acme_voice"})
    assert voice_providers(orch, pid) == "acme-es"


def test_spend_not_authorized_error_when_only_paid_available(system, tmp_path):
    _, registry, _, gateway, _ = system
    registry.add("mock_paid_image", credentials={"api_key": "key-1234567890"})
    registry.remove("mock_image")
    with pytest.raises(SpendNotAuthorized):
        gateway.invoke(C.IMAGE, "generate", ImageRequest(prompt="x", out_dir=tmp_path))
