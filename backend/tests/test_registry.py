"""Provider Registry: catálogo, credenciales cifradas, principal/alternativos, estado y pruebas."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from ytauto.core.errors import ProviderNotConfigured
from ytauto.db import schema as s
from ytauto.db.schema import make_engine
from ytauto.providers.contract import run_contract
from ytauto.providers.interfaces import ProviderCategory as C
from ytauto.providers.registry import (
    CredentialVault, ProviderRegistry, RegistryError, discover, load_or_create_master_key,
)
from ytauto.providers.registry.vault import VaultError


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path / "r.db")


@pytest.fixture
def registry(engine):
    return ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()), include_mocks=True)


# ------------------------------------------------------------------ catálogo
def test_discovery_finds_builtin_and_mock_adapters():
    names = set(discover(include_mocks=True))
    assert {"proportional", "mock_image", "mock_tts", "mock_render", "mock_paid_image"} <= names
    assert "mock_image" not in discover(include_mocks=False)


def test_register_adapter_validates_interface():
    from ytauto.providers.interfaces import BaseProvider, ProviderCategory
    from ytauto.providers.registry import register_adapter

    class NotAProvider(BaseProvider):
        category = ProviderCategory.TTS
        name = "bad"

    with pytest.raises(TypeError):
        register_adapter(NotAProvider)


# ------------------------------------------------------------------ credenciales
def test_credentials_are_encrypted_and_masked(engine, registry):
    registry.add("mock_paid_image", credentials={"api_key": "sk-super-secret-123456"})
    with engine.connect() as c:
        raw = c.execute(select(s.credentials.c.ciphertext)).scalar_one()
    assert "super-secret" not in raw
    view = next(v for v in registry.views() if v.id == "mock_paid_image")
    assert view.credentials == {"api_key": "••••3456"}
    assert "sk-super" not in view.model_dump_json()
    assert registry.instance("mock_paid_image").credentials["api_key"] == "sk-super-secret-123456"


def test_wrong_master_key_cannot_decrypt(engine):
    r1 = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()), include_mocks=True)
    r1.add("mock_paid_image", credentials={"api_key": "secret-value-123"})
    vault2 = CredentialVault(engine, Fernet.generate_key())
    with pytest.raises(VaultError):
        vault2.get_all("mock_paid_image")


def test_invalid_master_key_rejected(engine):
    with pytest.raises(VaultError):
        CredentialVault(engine, b"not-a-key")


def test_master_key_file_created_with_private_permissions(tmp_path):
    f = tmp_path / "secrets" / "master.key"
    k1 = load_or_create_master_key(None, f)
    assert (f.stat().st_mode & 0o777) == 0o600
    assert load_or_create_master_key(None, f) == k1
    assert load_or_create_master_key("env-key", f) == b"env-key"


def test_missing_credentials_prevent_instantiation(registry):
    registry.add("mock_paid_image")
    with pytest.raises(ProviderNotConfigured):
        registry.instance("mock_paid_image")
    view = registry.views()[0]
    assert view.missing_credentials == ["api_key"]
    with pytest.raises(RegistryError):
        registry.set_credential("mock_paid_image", "unknown_key", "x")


# ------------------------------------------------------------------ alta y selección
def test_add_enable_disable_remove(registry):
    registry.add("mock_tts")
    registry.add("mock_image", params={})
    with pytest.raises(RegistryError):
        registry.add("mock_tts")  # duplicado
    with pytest.raises(RegistryError):
        registry.add("no_existe")
    with pytest.raises(RegistryError):
        registry.add("mock_image", id="otra", params={"inventado": 1})
    registry.disable("mock_tts")
    assert registry.chain(C.TTS) == []
    registry.enable("mock_tts")
    assert [p.id for p in registry.chain(C.TTS)] == ["mock_tts"]
    registry.remove("mock_tts")
    assert registry.list(C.TTS) == []


def test_primary_and_fallback_order(registry):
    registry.add("mock_image", id="img_a")
    registry.add("mock_image", id="img_b")
    registry.add("mock_image", id="img_c")
    assert [p.id for p in registry.chain(C.IMAGE)] == ["img_a", "img_b", "img_c"]
    registry.set_primary(C.IMAGE, "img_c")
    assert registry.chain(C.IMAGE)[0].id == "img_c"
    registry.set_fallbacks(C.IMAGE, ["img_b"])
    assert [p.id for p in registry.chain(C.IMAGE)] == ["img_c", "img_b", "img_a"]
    roles = {v.id: v.role for v in registry.views(C.IMAGE)}
    assert roles == {"img_c": "primary", "img_b": "fallback", "img_a": "fallback"}
    with pytest.raises(RegistryError):
        registry.set_primary(C.TTS, "img_a")


def test_test_connection_runs_contract_and_records_status(registry):
    registry.add("mock_tts")
    report = registry.test("mock_tts")
    assert report.passed
    st = registry.status("mock_tts")
    assert st.healthy is True and st.last_check_at


def test_paid_provider_contract_skipped_to_avoid_costs(registry):
    registry.add("mock_paid_image", credentials={"api_key": "k-123456789"})
    report = registry.test("mock_paid_image")
    assert report.skipped and "costes" in report.skipped


def test_seed_defaults_registers_only_free_local_real_adapters(registry):
    added = registry.seed_defaults()
    assert "proportional" in added
    assert not any(a.startswith("mock") for a in added)
    assert registry.seed_defaults() == []  # idempotente


def test_errors_and_rate_limits_are_tracked(registry):
    registry.add("mock_tts")
    registry.record_error("mock_tts", "429 rate limited", retry_after_s=60)
    assert registry.is_rate_limited("mock_tts")
    assert registry.status("mock_tts").error_count == 1
    registry.record_success("mock_tts")
    assert not registry.is_rate_limited("mock_tts")


# ------------------------------------------------------------------ contratos de todos los adaptadores
@pytest.mark.parametrize("name", sorted(n for n, c in discover(include_mocks=True).items()
                                        if not n.startswith("failing")))
def test_every_adapter_satisfies_its_contract(name, tmp_path):
    cls = discover(include_mocks=True)[name]
    creds = {k: "test-credential-000" for k in cls.required_credentials}
    report = run_contract(cls(credentials=creds), workdir=tmp_path, allow_paid=True)
    failed = [f"{c.name}: {c.detail}" for c in report.checks if not c.passed]
    assert report.passed, f"{name} incumple el contrato: {failed}"
