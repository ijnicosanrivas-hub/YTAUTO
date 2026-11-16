"""Provider Registry: alta, activación, credenciales, principal/alternativos, estado y pruebas."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from ...core.errors import ProviderNotConfigured, YtautoError
from ...core.models import utcnow
from ...db import schema as s
from ..contract import ContractReport, run_contract
from ..interfaces import BaseProvider, CostEstimate, ProviderCategory
from . import catalog
from .vault import CredentialVault


class RegistryError(YtautoError):
    pass


class ProviderConfig(BaseModel):
    id: str
    adapter: str
    category: ProviderCategory
    display_name: str
    enabled: bool = True
    priority: int = 100
    params: dict[str, Any] = Field(default_factory=dict)
    monthly_budget_eur: float | None = None
    max_generations_per_project: int | None = None
    created_at: str = ""
    updated_at: str = ""


class ProviderStatus(BaseModel):
    last_check_at: str | None = None
    healthy: bool | None = None
    message: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None
    error_count: int = 0
    success_count: int = 0
    last_used_at: str | None = None
    rate_limited_until: float | None = None


class ProviderView(ProviderConfig):
    """Lo que ve la interfaz: nunca incluye credenciales en claro."""
    role: str  # primary | fallback | disabled
    is_paid: bool
    is_local: bool
    requires_network: bool = False
    required_credentials: list[str]
    credentials: dict[str, str]  # clave -> pista enmascarada
    missing_credentials: list[str]
    adapter_available: bool
    status: ProviderStatus
    capabilities: dict[str, Any] = Field(default_factory=dict)


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,62}$")


class ProviderRegistry:
    def __init__(self, engine: Engine, vault: CredentialVault, include_mocks: bool = False,
                 adapters: dict[str, type[BaseProvider]] | None = None, clock=time.time):
        self.engine = engine
        self.vault = vault
        self.include_mocks = include_mocks
        self._adapters = adapters
        self._cache: dict[str, BaseProvider] = {}
        self._health: dict[str, tuple[float, bool]] = {}
        self._lock = threading.RLock()
        self.clock = clock
        s.init_db(engine)

    # ------------------------------------------------------------------ catálogo
    def adapters(self) -> dict[str, type[BaseProvider]]:
        if self._adapters is None:
            return catalog.discover(self.include_mocks)
        return {**self._adapters, **catalog._EXTRA}

    def adapter_catalog(self) -> list[catalog.AdapterInfo]:
        return [catalog.info(c) for c in self.adapters().values()]

    # ------------------------------------------------------------------ CRUD
    def add(self, adapter: str, id: str | None = None, display_name: str | None = None,
            params: dict[str, Any] | None = None, enabled: bool = True, priority: int | None = None,
            credentials: dict[str, str] | None = None, monthly_budget_eur: float | None = None,
            max_generations_per_project: int | None = None) -> ProviderConfig:
        cls = self.adapters().get(adapter)
        if cls is None:
            raise RegistryError(f"Adaptador desconocido: {adapter}")
        pid = id or adapter
        if not _ID_RE.match(pid):
            raise RegistryError("Identificador inválido (minúsculas, números, '_' o '-')")
        unknown = set(params or {}) - set(cls.default_params)
        if unknown:
            raise RegistryError(f"Parámetros no admitidos por {adapter}: {sorted(unknown)}")
        if priority is None:
            existing = self.list(cls.category)
            priority = (max(p.priority for p in existing) + 10) if existing else 0
        now = utcnow().isoformat()
        with self.engine.begin() as c:
            if c.execute(select(s.provider_configs.c.id).where(s.provider_configs.c.id == pid)).first():
                raise RegistryError(f"Ya existe un proveedor con id '{pid}'")
            c.execute(insert(s.provider_configs).values(
                id=pid, adapter=adapter, category=cls.category.value, display_name=display_name or cls.display_name
                or adapter, enabled=enabled, priority=priority, params=params or {},
                monthly_budget_eur=monthly_budget_eur, max_generations_per_project=max_generations_per_project,
                created_at=now, updated_at=now))
            c.execute(insert(s.provider_status).values(provider_id=pid, error_count=0, success_count=0))
        for k, v in (credentials or {}).items():
            self.set_credential(pid, k, v)
        return self.get(pid)

    def get(self, pid: str) -> ProviderConfig:
        with self.engine.connect() as c:
            row = c.execute(select(s.provider_configs).where(s.provider_configs.c.id == pid)).mappings().first()
        if row is None:
            raise RegistryError(f"Proveedor inexistente: {pid}")
        return ProviderConfig(**dict(row))

    def list(self, category: ProviderCategory | None = None, enabled_only: bool = False) -> list[ProviderConfig]:
        q = select(s.provider_configs)
        if category:
            q = q.where(s.provider_configs.c.category == ProviderCategory(category).value)
        if enabled_only:
            q = q.where(s.provider_configs.c.enabled.is_(True))
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.provider_configs.c.category, s.provider_configs.c.priority,
                                        s.provider_configs.c.id)).mappings().all()
        return [ProviderConfig(**dict(r)) for r in rows]

    def update(self, pid: str, **fields: Any) -> ProviderConfig:
        allowed = {"display_name", "enabled", "priority", "params", "monthly_budget_eur", "max_generations_per_project"}
        bad = set(fields) - allowed
        if bad:
            raise RegistryError(f"Campos no editables: {sorted(bad)}")
        cfg = self.get(pid)
        if "params" in fields:
            cls = self.adapters().get(cfg.adapter)
            unknown = set(fields["params"] or {}) - set(cls.default_params if cls else {})
            if unknown:
                raise RegistryError(f"Parámetros no admitidos: {sorted(unknown)}")
        with self.engine.begin() as c:
            c.execute(update(s.provider_configs).where(s.provider_configs.c.id == pid)
                      .values(**fields, updated_at=utcnow().isoformat()))
        self._invalidate(pid)
        return self.get(pid)

    def remove(self, pid: str) -> None:
        self.get(pid)
        with self.engine.begin() as c:
            c.execute(delete(s.credentials).where(s.credentials.c.provider_id == pid))
            c.execute(delete(s.provider_status).where(s.provider_status.c.provider_id == pid))
            c.execute(delete(s.provider_configs).where(s.provider_configs.c.id == pid))
        self._invalidate(pid)

    def enable(self, pid: str) -> ProviderConfig:
        return self.update(pid, enabled=True)

    def disable(self, pid: str) -> ProviderConfig:
        return self.update(pid, enabled=False)

    # ------------------------------------------------------------------ principal / alternativos
    def set_primary(self, category: ProviderCategory, pid: str) -> list[ProviderConfig]:
        cfg = self.get(pid)
        if cfg.category != ProviderCategory(category):
            raise RegistryError(f"{pid} no pertenece a la categoría {category}")
        others = [p.id for p in self.list(category) if p.id != pid]
        return self.set_order(category, [pid, *others], enable=[pid])

    def set_fallbacks(self, category: ProviderCategory, fallback_ids: list[str]) -> list[ProviderConfig]:
        current = self.list(category)
        primary = next((p.id for p in current if p.enabled), None)
        rest = [p.id for p in current if p.id != primary and p.id not in fallback_ids]
        order = ([primary] if primary else []) + [f for f in fallback_ids if f != primary] + rest
        return self.set_order(category, order, enable=fallback_ids)

    def set_order(self, category: ProviderCategory, ids: list[str], enable: list[str] | None = None) -> list[ProviderConfig]:
        known = {p.id for p in self.list(category)}
        if set(ids) - known:
            raise RegistryError(f"Proveedores ajenos a la categoría: {sorted(set(ids) - known)}")
        with self.engine.begin() as c:
            for n, pid in enumerate(ids):
                values: dict[str, Any] = {"priority": n * 10, "updated_at": utcnow().isoformat()}
                if enable and pid in enable:
                    values["enabled"] = True
                c.execute(update(s.provider_configs).where(s.provider_configs.c.id == pid).values(**values))
        self._invalidate()
        return self.list(category)

    def chain(self, category: ProviderCategory) -> list[ProviderConfig]:
        """Cadena de uso: principal + alternativos activos, en orden."""
        return self.list(category, enabled_only=True)

    # ------------------------------------------------------------------ credenciales
    def set_credential(self, pid: str, key: str, value: str) -> str:
        cfg = self.get(pid)
        cls = self.adapters().get(cfg.adapter)
        if cls and cls.required_credentials and key not in cls.required_credentials:
            raise RegistryError(f"{cfg.adapter} no usa la credencial '{key}' (admite: {cls.required_credentials})")
        hint = self.vault.set(pid, key, value)
        self._invalidate(pid)
        return hint

    def delete_credential(self, pid: str, key: str) -> None:
        self.vault.delete(pid, key)
        self._invalidate(pid)

    def missing_credentials(self, cfg: ProviderConfig) -> list[str]:
        cls = self.adapters().get(cfg.adapter)
        have = set(self.vault.hints(cfg.id))
        return [k for k in (cls.required_credentials if cls else []) if k not in have]

    # ------------------------------------------------------------------ instancias
    def instance(self, pid: str) -> BaseProvider:
        with self._lock:
            if pid in self._cache:
                return self._cache[pid]
            cfg = self.get(pid)
            cls = self.adapters().get(cfg.adapter)
            if cls is None:
                raise ProviderNotConfigured(f"El adaptador '{cfg.adapter}' no está instalado")
            missing = self.missing_credentials(cfg)
            if missing:
                raise ProviderNotConfigured(f"{pid}: faltan credenciales {missing}")
            inst = cls(params=cfg.params, credentials=self.vault.get_all(pid))
            self._cache[pid] = inst
            return inst

    def _invalidate(self, pid: str | None = None) -> None:
        with self._lock:
            if pid is None:
                self._cache.clear()
                self._health.clear()
            else:
                self._cache.pop(pid, None)
                self._health.pop(pid, None)

    # ------------------------------------------------------------------ estado
    def status(self, pid: str) -> ProviderStatus:
        with self.engine.connect() as c:
            row = c.execute(select(s.provider_status).where(s.provider_status.c.provider_id == pid)).mappings().first()
        return ProviderStatus(**{k: v for k, v in dict(row).items() if k != "provider_id"}) if row else ProviderStatus()

    def _upsert_status(self, pid: str, **values: Any) -> None:
        stmt = sqlite_insert(s.provider_status).values(provider_id=pid, **values)
        with self.engine.begin() as c:
            c.execute(stmt.on_conflict_do_update(index_elements=["provider_id"], set_=values))

    def record_success(self, pid: str) -> None:
        st = self.status(pid)
        self._upsert_status(pid, success_count=st.success_count + 1, last_used_at=utcnow().isoformat(),
                            rate_limited_until=None)

    def record_error(self, pid: str, message: str, retry_after_s: float | None = None) -> None:
        st = self.status(pid)
        values: dict[str, Any] = {"error_count": st.error_count + 1, "last_error": message[:1000],
                                  "last_error_at": utcnow().isoformat()}
        if retry_after_s:
            values["rate_limited_until"] = self.clock() + retry_after_s
        self._upsert_status(pid, **values)

    def is_healthy(self, pid: str, ttl_s: float = 60.0) -> bool:
        """Comprobación de salud con caché (evita lanzar trabajo a proveedores no disponibles)."""
        now = self.clock()
        cached = self._health.get(pid)
        if cached and now - cached[0] < ttl_s:
            return cached[1]
        try:
            h = self.instance(pid).health_check()
            ok, msg = h.ok, h.message
        except Exception as e:  # noqa: BLE001
            ok, msg = False, str(e)
        self._health[pid] = (now, ok)
        self._upsert_status(pid, healthy=ok, message=msg, last_check_at=utcnow().isoformat())
        return ok

    def is_rate_limited(self, pid: str) -> bool:
        until = self.status(pid).rate_limited_until
        return until is not None and until > self.clock()

    def test(self, pid: str, run_contract_tests: bool = True, allow_paid: bool = False,
             workdir: Path | None = None) -> ContractReport:
        """'Probar conexión' del panel: health_check + batería de contrato (sin costes por defecto)."""
        cfg = self.get(pid)
        try:
            inst = self.instance(pid)
        except ProviderNotConfigured as e:
            self._upsert_status(pid, last_check_at=utcnow().isoformat(), healthy=False, message=str(e))
            return ContractReport(provider=pid, category=cfg.category.value, passed=False, skipped=str(e))
        if inst.requires_network:
            # Un servicio externo nunca ejecuta la batería de contrato contra el servicio real (costaría
            # dinero o publicaría): solo una comprobación de lectura y sin coste.
            from ..contract import ContractCheck
            h = inst.verify_connection()
            report = ContractReport(provider=pid, category=cfg.category.value, passed=h.ok,
                                    checks=[ContractCheck(name="conexión", passed=h.ok, detail=h.message)])
        elif run_contract_tests:
            report = run_contract(inst, workdir=workdir, allow_paid=allow_paid)
        else:
            h = inst.health_check()
            from ..contract import ContractCheck
            report = ContractReport(provider=pid, category=cfg.category.value, passed=h.ok,
                                    checks=[ContractCheck(name="health_check", passed=h.ok, detail=h.message)])
        failed = [c.name for c in report.checks if not c.passed]
        self._upsert_status(pid, last_check_at=utcnow().isoformat(), healthy=report.passed,
                            message=report.skipped or ("OK" if report.passed else f"Fallos: {failed}"))
        return report

    def estimate(self, pid: str, operation: str, request: BaseModel) -> CostEstimate:
        inst = self.instance(pid)
        return inst.estimate_cost(operation, request) if inst.is_paid else CostEstimate(detail="gratuito/local")

    # ------------------------------------------------------------------ vistas para la interfaz
    def views(self, category: ProviderCategory | None = None) -> list[ProviderView]:
        adapters = self.adapters()
        out = []
        primaries: dict[str, str] = {}
        for cfg in self.list(category):
            if cfg.enabled and cfg.category.value not in primaries:
                primaries[cfg.category.value] = cfg.id
        for cfg in self.list(category):
            cls = adapters.get(cfg.adapter)
            caps: dict[str, Any] = {}
            if cls:
                try:
                    caps = cls(params=cfg.params).capabilities()
                except Exception:  # noqa: BLE001
                    caps = {}
            role = "disabled" if not cfg.enabled else ("primary" if primaries.get(cfg.category.value) == cfg.id
                                                       else "fallback")
            out.append(ProviderView(
                **cfg.model_dump(), role=role, is_paid=bool(cls and cls.is_paid), is_local=bool(cls and cls.is_local),
                requires_network=bool(cls and cls.requires_network), required_credentials=list(cls.required_credentials) if cls else [],
                credentials=self.vault.hints(cfg.id), missing_credentials=self.missing_credentials(cfg),
                adapter_available=cls is not None, status=self.status(cfg.id), capabilities=caps,
            ))
        return out

    def seed_defaults(self) -> list[str]:
        """Primer arranque: registra los adaptadores locales y gratuitos incluidos."""
        added = []
        existing = {p.adapter for p in self.list()}
        # Solo se dan de alta adaptadores nunca vistos: si el usuario quita uno, no reaparece.
        with self.engine.connect() as c:
            row = c.execute(select(s.app_settings.c.value).where(s.app_settings.c.key == "seeded_adapters")).first()
        seeded = set(row[0] if row else [])
        existing |= seeded
        for name, cls in sorted(self.adapters().items(), key=lambda kv: (kv[1].default_priority, kv[0])):
            if cls.is_paid or not cls.is_local or cls.required_credentials or name in existing:
                continue
            if cls.__module__.startswith("ytauto.providers.mock"):
                continue
            if getattr(cls, "auto_register", True):
                self.add(name, priority=cls.default_priority)
                added.append(name)
        all_seeded = sorted(seeded | set(added) | {p.adapter for p in self.list()})
        stmt = sqlite_insert(s.app_settings).values(key="seeded_adapters", value=all_seeded)
        with self.engine.begin() as c:
            c.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": all_seeded}))
        return added
