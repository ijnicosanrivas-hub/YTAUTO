"""Construcción del sistema de proveedores a partir de la base de datos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy.engine import Engine

from ..core.events import EventBus
from .registry import BudgetManager, CredentialVault, ProviderRegistry, RegistryGateway, load_or_create_master_key


@dataclass
class ProviderSystem:
    registry: ProviderRegistry
    budget: BudgetManager
    gateway: RegistryGateway
    vault: CredentialVault


def build_provider_system(engine: Engine, data_dir: Path, master_key: str | None, events: EventBus | None = None,
                          include_mocks: bool = False, seed: bool = True,
                          project_budget: Callable[[str], float | None] | None = None,
                          is_spend_authorized: Callable[[str | None, str], bool] | None = None,
                          preferred: Callable[[str | None], dict[str, str]] | None = None) -> ProviderSystem:
    key = load_or_create_master_key(master_key, data_dir / "secrets" / "master.key")
    vault = CredentialVault(engine, key)
    registry = ProviderRegistry(engine, vault, include_mocks=include_mocks)
    if seed:
        registry.seed_defaults()
    budget = BudgetManager(
        engine, project_budget=project_budget,
        on_warning=(lambda msg, data: events.emit("budget.warning", project_id=data.get("project_id"),
                                                  data={"message": msg, **data})) if events else None)
    authorized_global = lambda pid, prov: prov in (budget.get_setting("spend_authorized_providers", []) or [])  # noqa: E731
    gateway = RegistryGateway(
        registry, budget,
        is_spend_authorized=lambda pid, prov: authorized_global(pid, prov) or
        bool(is_spend_authorized and is_spend_authorized(pid, prov)),
        preferred=preferred, events=events)
    return ProviderSystem(registry=registry, budget=budget, gateway=gateway, vault=vault)
