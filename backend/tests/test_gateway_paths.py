"""Rutas de error del gateway: lo que protege el gasto cuando un proveedor falla a mitad."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from ytauto.core.errors import ProviderError, ProviderNotConfigured
from ytauto.db.schema import make_engine
from ytauto.providers.interfaces import HealthStatus, ImageRequest, ProviderCategory as C
from ytauto.providers.mock import MockPaidImageProvider
from ytauto.providers.registry import (
    BudgetManager, CredentialVault, ProviderRegistry, RegistryGateway, register_adapter, unregister_adapter,
)


class PaidBoom(MockPaidImageProvider):
    """Proveedor de pago que falla de distintas formas según `mode`."""
    name = "paid_boom"
    mode = "provider_error"

    def generate(self, request):
        if self.mode == "provider_error":
            raise ProviderError(self.name, "servicio caído", transient=True)
        if self.mode == "generic":
            raise RuntimeError("fallo inesperado del SDK")
        raise ProviderNotConfigured("sin configurar a mitad")


class PaidSick(MockPaidImageProvider):
    name = "paid_sick"

    def health_check(self):
        return HealthStatus(ok=False, message="no disponible")


@pytest.fixture
def env(tmp_path):
    register_adapter(PaidBoom)
    register_adapter(PaidSick)
    engine = make_engine(tmp_path / "g.db")
    reg = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()), include_mocks=True)
    reg.add("paid_boom", credentials={"api_key": "k-123456789"})
    reg.add("mock_image")  # alternativa gratuita, después de la de pago
    clock = {"t": 1000.0}
    reg.clock = lambda: clock["t"]
    budget = BudgetManager(engine, project_budget=lambda pid: 5.0)
    gw = RegistryGateway(reg, budget, is_spend_authorized=lambda pid, prov: True)
    yield reg, budget, gw, clock, tmp_path
    unregister_adapter("paid_boom")
    unregister_adapter("paid_sick")


@pytest.mark.parametrize("mode", ["provider_error", "generic", "not_configured"])
def test_paid_provider_failing_midway_releases_the_reservation_and_falls_back(env, mode):
    reg, budget, gw, _, tmp = env
    PaidBoom.mode = mode
    asset = gw.invoke(C.IMAGE, "generate", ImageRequest(prompt="x", out_dir=tmp), project_id="p1")
    assert asset.provider == "mock_image"  # respondió la alternativa gratuita
    assert budget.spent_project("p1") == 0 and budget.ledger("p1") == []  # no se contó un gasto que no ocurrió
    assert reg.status("paid_boom").error_count == (0 if mode == "not_configured" else 1)


def test_rate_limited_provider_is_skipped_until_it_resets(env):
    reg, _, gw, clock, tmp = env
    PaidBoom.mode = "provider_error"
    reg.record_error("paid_boom", "429", retry_after_s=60)
    assert gw.invoke(C.IMAGE, "generate", ImageRequest(prompt="x", out_dir=tmp)).provider == "mock_image"
    assert reg.is_rate_limited("paid_boom")
    clock["t"] += 61
    assert not reg.is_rate_limited("paid_boom")


def test_unhealthy_provider_is_skipped_and_all_failing_raises_aggregated_error(env):
    reg, _, gw, _, tmp = env
    register_adapter(PaidSick)
    reg.add("paid_sick", credentials={"api_key": "k-123456789"})
    reg.set_order(C.IMAGE, ["paid_sick"])
    reg.disable("mock_image")
    reg.disable("paid_boom")
    with pytest.raises(ProviderError) as e:
        gw.invoke(C.IMAGE, "generate", ImageRequest(prompt="x", out_dir=tmp), project_id="p1")
    assert "health check" in str(e.value)


def test_empty_chain_and_query_fallthrough(env):
    reg, _, gw, _, tmp = env
    with pytest.raises(ProviderNotConfigured):
        gw.invoke(C.TTS, "synthesize", object())
    with pytest.raises(ProviderNotConfigured):
        gw.query(C.TTS, "list_voices")
    # query: el primero falla, responde el segundo; si fallan todos, error claro
    calls = []

    def flaky(*a, **k):
        calls.append("boom")
        raise RuntimeError("no")

    PaidBoom.capabilities = lambda self: flaky()
    assert gw.query(C.IMAGE, "capabilities")  # paid_boom falla; mock_image responde
    assert calls == ["boom"]
    reg.disable("mock_image")
    with pytest.raises(ProviderError) as e:
        gw.query(C.IMAGE, "capabilities")
    assert "Consulta 'capabilities' fallida" in str(e.value)
    del PaidBoom.capabilities
