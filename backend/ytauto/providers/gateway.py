"""Pasarela directa: un proveedor fijo por categoría (pruebas y configuraciones mínimas).

La pasarela con registro, alternativas, presupuesto y autorización de gasto es
`ytauto.providers.registry.RegistryGateway`.
"""
from __future__ import annotations

from typing import Any

from ..core.errors import ProviderNotConfigured
from .interfaces import BaseProvider, ProviderCategory, ProviderGateway


class DirectGateway(ProviderGateway):
    def __init__(self, providers: dict[ProviderCategory, BaseProvider]):
        self.providers = providers

    def _get(self, category: ProviderCategory) -> BaseProvider:
        p = self.providers.get(category)
        if p is None:
            raise ProviderNotConfigured(f"No hay proveedor configurado para '{category.value}'")
        return p

    def invoke(self, category, operation, request, *, project_id=None, scene_index=None) -> Any:
        return getattr(self._get(category), operation)(request)

    def query(self, category, operation, *args, project_id=None, **kwargs) -> Any:
        return getattr(self._get(category), operation)(*args, **kwargs)
