"""Catálogo de adaptadores disponibles (descubrimiento automático).

Fuentes, en este orden:
1. Módulos dentro de `ytauto.providers.<categoría>` (adaptadores incluidos).
2. Paquetes externos que declaren el entry point `ytauto.providers` (adaptadores instalados
   con pip, sin tocar este repositorio).
3. Registro explícito con `register_adapter()` (pruebas o extensiones en caliente).

Añadir un proveedor nuevo = crear su clase (heredando de la interfaz de su categoría) en
uno de esos lugares. No hay que modificar agentes ni orquestador.
"""
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from importlib.metadata import entry_points
from typing import Any

from pydantic import BaseModel

from ..interfaces import INTERFACE_BY_CATEGORY, BaseProvider, ProviderCategory

log = logging.getLogger("ytauto.providers.catalog")

BUILTIN_PACKAGES = ("image", "video", "voice", "music", "sound", "subtitle", "rendering", "storage", "publishing")
# Los simulados solo se exponen si se piden (pruebas / demostración).
MOCK_PACKAGE = "mock"

_EXTRA: dict[str, type[BaseProvider]] = {}


class AdapterInfo(BaseModel):
    name: str
    category: ProviderCategory
    display_name: str
    is_paid: bool
    is_local: bool
    required_credentials: list[str]
    default_params: dict[str, Any]
    module: str
    doc: str = ""


def register_adapter(cls: type[BaseProvider]) -> type[BaseProvider]:
    _validate(cls)
    _EXTRA[cls.name] = cls
    return cls


def unregister_adapter(name: str) -> None:
    _EXTRA.pop(name, None)


def _validate(cls: type[BaseProvider]) -> None:
    if inspect.isabstract(cls):
        raise TypeError(f"{cls.__name__} no implementa todos los métodos de su interfaz")
    cat = getattr(cls, "category", None)
    if cat not in INTERFACE_BY_CATEGORY or not issubclass(cls, INTERFACE_BY_CATEGORY[cat]):
        raise TypeError(f"{cls.__name__} debe heredar de la interfaz de su categoría")
    if not getattr(cls, "name", None):
        raise TypeError(f"{cls.__name__} no define 'name'")


def _classes_in(module) -> list[type[BaseProvider]]:
    out = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, BaseProvider) and obj.__module__ == module.__name__ and not inspect.isabstract(obj) \
                and getattr(obj, "name", None) and "name" in obj.__dict__:
            out.append(obj)
    return out


def discover(include_mocks: bool = False) -> dict[str, type[BaseProvider]]:
    found: dict[str, type[BaseProvider]] = {}
    pkgs = list(BUILTIN_PACKAGES) + ([MOCK_PACKAGE] if include_mocks else [])
    for pkg_name in pkgs:
        try:
            pkg = importlib.import_module(f"ytauto.providers.{pkg_name}")
        except ModuleNotFoundError:
            continue
        modules = [pkg]
        for m in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
            try:
                modules.append(importlib.import_module(f"{pkg.__name__}.{m.name}"))
            except Exception as e:  # noqa: BLE001 - un adaptador roto no debe tumbar el sistema
                log.warning("No se pudo cargar el adaptador %s.%s: %s", pkg.__name__, m.name, e)
        for mod in modules:
            for cls in _classes_in(mod):
                found[cls.name] = cls
    for ep in entry_points(group="ytauto.providers"):
        try:
            cls = ep.load()
            _validate(cls)
            found[cls.name] = cls
        except Exception as e:  # noqa: BLE001
            log.warning("Entry point de proveedor inválido %s: %s", ep.name, e)
    found.update(_EXTRA)
    return found


def info(cls: type[BaseProvider]) -> AdapterInfo:
    return AdapterInfo(
        name=cls.name, category=cls.category, display_name=cls.display_name or cls.name, is_paid=cls.is_paid,
        is_local=cls.is_local, required_credentials=list(cls.required_credentials),
        default_params=dict(cls.default_params), module=cls.__module__,
        doc=(inspect.getdoc(cls) or "").split("\n\n")[0],
    )
