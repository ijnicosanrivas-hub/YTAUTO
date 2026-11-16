"""Pasarela respaldada por el registro: principal → alternativos, presupuesto y autorización.

Reglas:
- Se prueba la cadena de la categoría en orden (preferencia del proyecto primero).
- Un proveedor de pago solo se usa si el gasto está autorizado y cabe en el presupuesto.
  Si no, se salta: el fallback NUNCA cambia a un servicio de pago sin autorización.
- Si al final ningún proveedor pudo usarse por falta de autorización/presupuesto, la fase se
  bloquea con un mensaje claro para que el usuario decida (no hay gasto silencioso).
- Proveedores con límite de uso activo (rate limit) se saltan hasta su hora de reinicio.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ...core.errors import BudgetExceeded, ProviderError, ProviderNotConfigured, SpendNotAuthorized
from ...core.events import EventBus
from ...core.models import MediaAsset
from ..interfaces import ProviderCategory, ProviderGateway, PublishRequest
from .budget import BudgetManager
from .registry import ProviderConfig, ProviderRegistry

log = logging.getLogger("ytauto.providers.gateway")


class RegistryGateway(ProviderGateway):
    def __init__(self, registry: ProviderRegistry, budget: BudgetManager,
                 is_spend_authorized: Callable[[str | None, str], bool] | None = None,
                 preferred: Callable[[str | None], dict[str, str]] | None = None,
                 events: EventBus | None = None):
        self.registry = registry
        self.budget = budget
        self.is_spend_authorized = is_spend_authorized or (lambda project_id, provider_id: False)
        self.preferred = preferred or (lambda project_id: {})
        self.events = events

    def _emit(self, type_: str, project_id: str | None, data: dict[str, Any]) -> None:
        if self.events:
            self.events.emit(type_, project_id=project_id, data=data)

    def candidates(self, category: ProviderCategory, project_id: str | None, request: Any = None) -> list[ProviderConfig]:
        chain = self.registry.chain(category)
        pref = self.preferred(project_id).get(category.value)
        if pref:
            chain.sort(key=lambda c: 0 if c.id == pref or c.adapter == pref else 1)
        if category is ProviderCategory.PUBLISHING and isinstance(request, PublishRequest):
            filtered = []
            for cfg in chain:
                cls = self.registry.adapters().get(cfg.adapter)
                if cls and request.platform in getattr(cls, "platforms", []):
                    filtered.append(cfg)
            chain = filtered
        return chain

    # ------------------------------------------------------------------ operaciones con coste potencial
    def invoke(self, category, operation, request, *, project_id=None, scene_index=None) -> Any:
        category = ProviderCategory(category)
        chain = self.candidates(category, project_id, request)
        if not chain:
            raise ProviderNotConfigured(f"No hay ningún proveedor activo para '{category.value}'")
        blocked_spend: list[str] = []
        blocked_budget: list[str] = []
        errors: list[ProviderError] = []
        for i, cfg in enumerate(chain):
            if self.registry.is_rate_limited(cfg.id):
                errors.append(ProviderError(cfg.id, "límite de uso del proveedor activo", transient=True))
                continue
            try:
                prov = self.registry.instance(cfg.id)
            except ProviderNotConfigured as e:
                errors.append(ProviderError(cfg.id, str(e), transient=False))
                continue
            if not self.registry.is_healthy(cfg.id):
                errors.append(ProviderError(cfg.id, "no disponible (health check)", transient=False))
                continue
            entry_id = None
            estimate = 0.0
            if prov.is_paid:
                estimate = prov.estimate_cost(operation, request).amount_eur
                if not self.is_spend_authorized(project_id, cfg.id):
                    blocked_spend.append(f"{cfg.display_name} (≈{estimate:.2f} €/operación)")
                    continue
                check = self.budget.check(project_id=project_id, provider_id=cfg.id, amount=estimate,
                                          provider_monthly_budget=cfg.monthly_budget_eur,
                                          max_generations=cfg.max_generations_per_project)
                for w in check.warnings:
                    self._emit("budget.warning", project_id, {"message": w, "provider_id": cfg.id})
                if not check.allowed:
                    blocked_budget.append(check.reason)
                    continue
                entry_id = self.budget.reserve(project_id=project_id, provider_id=cfg.id, category=category.value,
                                               operation=operation, amount=estimate, scene_index=scene_index)
            try:
                result = getattr(prov, operation)(request)
            except ProviderError as e:
                if entry_id is not None:
                    self.budget.fail(entry_id)
                self.registry.record_error(cfg.id, str(e), getattr(e, "retry_after_s", None))
                errors.append(e)
                log.warning("Proveedor %s falló en %s: %s", cfg.id, operation, e)
                continue
            except ProviderNotConfigured as e:
                if entry_id is not None:
                    self.budget.fail(entry_id)
                errors.append(ProviderError(cfg.id, str(e), transient=False))
                continue
            except Exception as e:  # noqa: BLE001 - cualquier fallo del adaptador activa el fallback
                if entry_id is not None:
                    self.budget.fail(entry_id)
                self.registry.record_error(cfg.id, f"{type(e).__name__}: {e}")
                errors.append(ProviderError(cfg.id, f"{type(e).__name__}: {e}", transient=False))
                continue
            if entry_id is not None:
                actual = result.cost_eur if isinstance(result, MediaAsset) and result.cost_eur else None
                self.budget.commit(entry_id, actual if actual is not None else estimate)
                self._emit("cost", project_id, {"provider_id": cfg.id, "operation": operation,
                                                "eur": actual if actual is not None else estimate})
            if isinstance(result, MediaAsset):
                result.metadata.setdefault("provider_instance", cfg.id)
            self.registry.record_success(cfg.id)
            if i > 0:
                self._emit("provider.fallback", project_id, {
                    "category": category.value, "used": cfg.id, "skipped": [c.id for c in chain[:i]],
                    "errors": [str(e) for e in errors]})
            return result

        if blocked_spend and not errors:
            raise SpendNotAuthorized(
                f"Para '{category.value}' solo quedan proveedores de pago sin autorización: "
                f"{', '.join(blocked_spend)}. Autoriza el gasto o configura una alternativa gratuita.")
        if blocked_budget and not errors:
            raise BudgetExceeded("; ".join(blocked_budget))
        if blocked_spend or blocked_budget:
            detail = "; ".join([*blocked_spend, *blocked_budget])
            last = errors[-1]
            raise ProviderError(last.provider, f"{last} (además, sin autorización/presupuesto: {detail})",
                                transient=any(e.transient for e in errors))
        last = errors[-1]
        raise ProviderError(last.provider, " | ".join(str(e) for e in errors), transient=any(e.transient for e in errors))

    # ------------------------------------------------------------------ consultas sin coste
    def query(self, category, operation, *args, project_id=None, **kwargs) -> Any:
        category = ProviderCategory(category)
        chain = self.candidates(category, project_id)
        if not chain:
            raise ProviderNotConfigured(f"No hay ningún proveedor activo para '{category.value}'")
        last: Exception | None = None
        healthy = [c for c in chain if self.registry.is_healthy(c.id)] or chain
        for cfg in healthy:
            try:
                return getattr(self.registry.instance(cfg.id), operation)(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                last = e
        raise ProviderError(chain[-1].id, f"Consulta '{operation}' fallida: {last}")

