"""Construcción de la pasarela de proveedores para la aplicación.

Fase 3: solo hay proveedores locales mínimos. La fase 4 sustituye esto por el
`ProviderRegistry` (activación, credenciales, alternativas y presupuesto).
"""
from __future__ import annotations

from .gateway import DirectGateway
from .interfaces import ProviderCategory
from .subtitle.proportional import ProportionalSubtitleProvider


def build_gateway() -> DirectGateway:
    return DirectGateway({ProviderCategory.SUBTITLE: ProportionalSubtitleProvider()})
