"""Licencias de Claude por canal y enrutado de cada llamada a la licencia elegida.

- `claude_session`: una sesión de Claude Code con su propia carpeta de configuración (`CLAUDE_CONFIG_DIR`),
  iniciada una vez con `claude /login` en esa carpeta. Cada licencia es una cuenta/suscripción distinta.
- `api_key`: una clave de la API de Anthropic (facturación por uso), guardada cifrada.

Reglas: nunca se lanzan dos llamadas a la vez con la misma licencia (un candado por licencia); una licencia
agotada no se usa hasta su reinicio; NO se salta automáticamente a la licencia de otro canal: eso lo decide
el usuario en la pantalla de asignación antes de lanzar (o reasignando y reanudando el proyecto).
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from ..core.errors import YtautoError
from ..core.models import ProjectSpec, utcnow
from ..db import schema as s
from .base import LLMProvider, LLMRequest, LLMResponse, UsageLimitError

LicenseKind = Literal["claude_session", "api_key"]
_ID = re.compile(r"^lic_[a-z0-9]{6,16}$")


class LicenseError(YtautoError):
    pass


class License(BaseModel):
    id: str
    name: str
    channel_id: str
    kind: LicenseKind
    plan: str = ""
    config_dir: str | None = None
    secret_hint: str | None = None
    monthly_token_limit: int | None = None
    enabled: bool = True
    is_limited: bool = False
    limited_until: float | None = None
    limited_reason: str | None = None
    last_used_at: str | None = None
    notes: str | None = None
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())

    def limited_now(self, now: float | None = None) -> bool:
        if not self.is_limited:
            return False
        return self.limited_until is None or (now or time.time()) < self.limited_until


class LicenseInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    channel_id: str
    kind: LicenseKind = "claude_session"
    plan: str = Field(default="", max_length=40)
    config_dir: str | None = None
    api_key: str | None = None  # solo de entrada; nunca se devuelve
    monthly_token_limit: int | None = Field(default=None, ge=0)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=500)


def _mask(v: str) -> str:
    return "••••" + v[-4:] if len(v) > 8 else "••••"


class LicenseStore:
    def __init__(self, engine: Engine, master_key: bytes, data_dir: Path):
        self.engine = engine
        self._fernet = Fernet(master_key)
        self.data_dir = data_dir
        s.init_db(engine)

    # ------------------------------------------------------------------ lectura
    def list(self, channel_id: str | None = None) -> list[License]:
        q = select(s.licenses)
        if channel_id:
            q = q.where(s.licenses.c.channel_id == channel_id)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.licenses.c.created_at)).mappings().all()
        return [self._from(r) for r in rows]

    def get(self, lid: str) -> License:
        with self.engine.connect() as c:
            r = c.execute(select(s.licenses).where(s.licenses.c.id == lid)).mappings().first()
        if r is None:
            raise KeyError(lid)
        return self._from(r)

    def secret(self, lid: str) -> str | None:
        with self.engine.connect() as c:
            token = c.execute(select(s.licenses.c.secret_cipher).where(s.licenses.c.id == lid)).scalar()
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as e:
            raise LicenseError("No se puede descifrar la clave de la licencia: ¿ha cambiado la clave maestra?") from e

    # ------------------------------------------------------------------ escritura
    def create(self, data: LicenseInput) -> License:
        lid = f"lic_{uuid.uuid4().hex[:10]}"
        row = self._row(lid, data)
        row["created_at"] = utcnow().isoformat()
        with self.engine.begin() as c:
            c.execute(insert(s.licenses).values(**row))
        return self.get(lid)

    def update(self, lid: str, data: LicenseInput) -> License:
        self.get(lid)
        row = self._row(lid, data, keep_secret=not data.api_key)
        row.pop("id")
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid).values(**row))
        return self.get(lid)

    def delete(self, lid: str) -> None:
        with self.engine.begin() as c:
            c.execute(s.licenses.delete().where(s.licenses.c.id == lid))

    def mark_limited(self, lid: str, resets_at: str | None, reason: str) -> None:
        until = float(resets_at) if resets_at and resets_at.strip().isdigit() else None
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid)
                      .values(is_limited=True, limited_until=until, limited_reason=reason[:300]))

    def clear_limit(self, lid: str) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid)
                      .values(is_limited=False, limited_until=None, limited_reason=None))

    def touch(self, lid: str) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid).values(last_used_at=utcnow().isoformat()))

    def default_config_dir(self, lid: str) -> Path:
        return self.data_dir / "licencias" / lid

    # ------------------------------------------------------------------ conversión
    def _row(self, lid: str, d: LicenseInput, keep_secret: bool = False) -> dict[str, Any]:
        row: dict[str, Any] = {"id": lid, "name": d.name.strip(), "channel_id": d.channel_id, "kind": d.kind,
                               "plan": d.plan.strip(), "monthly_token_limit": d.monthly_token_limit,
                               "enabled": d.enabled, "notes": d.notes}
        if d.kind == "claude_session":
            folder = Path(d.config_dir).expanduser() if d.config_dir else self.default_config_dir(lid)
            folder.mkdir(parents=True, exist_ok=True)
            row.update(config_dir=str(folder), secret_cipher=None, secret_hint=None)
        else:
            row["config_dir"] = None
            if d.api_key:
                key = d.api_key.strip()
                row.update(secret_cipher=self._fernet.encrypt(key.encode()).decode(), secret_hint=_mask(key))
            elif not keep_secret:
                raise LicenseError("Una licencia de tipo «clave de API» necesita la clave")
        return row

    @staticmethod
    def _from(r: Any) -> License:
        return License(**{k: r[k] for k in License.model_fields if k in r.keys()})


# ---------------------------------------------------------------------------- enrutado

ProviderFactory = Callable[[License, "str | None"], LLMProvider]


class LicenseRouter(LLMProvider):
    """Atiende cada llamada con la licencia asignada al agente en ese proyecto (o la del canal)."""

    name = "licencias"

    def __init__(self, store: LicenseStore, default: LLMProvider, factory: ProviderFactory,
                 spec_lookup: Callable[[str], ProjectSpec]):
        self.store = store
        self.default = default
        self.factory = factory
        self.spec_lookup = spec_lookup
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._cache: dict[str, tuple[tuple[Any, ...], LLMProvider]] = {}
        self._guard = threading.Lock()

    def resolve(self, project_id: str | None, agent: str) -> License | None:
        """Licencia que usará `agent` en el proyecto. None = sesión única por defecto (sin licencias)."""
        if not project_id:
            return None
        try:
            spec = self.spec_lookup(project_id)
        except KeyError:
            return None
        return self.resolve_for(spec.channel, spec.license_map, agent)

    def resolve_for(self, channel: str, license_map: dict[str, str], agent: str) -> License | None:
        wanted = license_map.get(agent)
        if wanted:
            try:
                lic = self.store.get(wanted)
                if lic.enabled:
                    return lic
            except KeyError:
                pass
        own = [lic for lic in self.store.list(channel) if lic.enabled]
        free = [lic for lic in own if not lic.limited_now()]
        return (free or own or [None])[0]

    def _provider(self, lic: License) -> LLMProvider:
        key = (lic.kind, lic.config_dir, lic.secret_hint)
        with self._guard:
            hit = self._cache.get(lic.id)
            if hit and hit[0] == key:
                return hit[1]
            provider = self.factory(lic, self.store.secret(lic.id) if lic.kind == "api_key" else None)
            self._cache[lic.id] = (key, provider)
            return provider

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self._complete_with(self.resolve(request.project_id, request.agent), request)

    def complete_for(self, channel: str, license_map: dict[str, str], request: LLMRequest) -> LLMResponse:
        """Llamada sin proyecto todavía (p. ej. la entrevista del director): licencia del canal."""
        return self._complete_with(self.resolve_for(channel, license_map, request.agent), request)

    def _complete_with(self, lic: License | None, request: LLMRequest) -> LLMResponse:
        if lic is None:
            with self._locks["default"]:  # la sesión única tampoco atiende dos llamadas a la vez
                return self.default.complete(request)
        if lic.is_limited and not lic.limited_now():
            self.store.clear_limit(lic.id)  # ya pasó la hora de reinicio
        elif lic.limited_now():
            raise UsageLimitError(f"La licencia «{lic.name}» está agotada: {lic.limited_reason or 'límite de uso'}",
                                  resets_at=str(int(lic.limited_until)) if lic.limited_until else None,
                                  license_id=lic.id)
        provider = self._provider(lic)
        with self._locks[lic.id]:  # nunca dos llamadas simultáneas con la misma cuenta
            try:
                response = provider.complete(request)
            except UsageLimitError as e:
                e.license_id = lic.id
                self.store.mark_limited(lic.id, e.resets_at, str(e))
                raise
        response.usage.license_id = lic.id
        self.store.touch(lic.id)
        return response

    def health_check(self) -> tuple[bool, str]:
        return self.default.health_check()


# ---------------------------------------------------------------------------- estadísticas

def _tokens(u: dict[str, Any]) -> int:
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_tokens"))


def usage_stats(licenses: list[License], usage: list[dict[str, Any]], project_channel: dict[str, str],
                now: datetime | None = None, days: int = 14) -> dict[str, Any]:
    """Estadísticas de consumo por licencia (más la sesión por defecto, `default`)."""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    month = now.strftime("%Y-%m")
    span = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    def empty() -> dict[str, Any]:
        return {"tokens": {"today": 0, "d7": 0, "d30": 0, "month": 0}, "calls": {"today": 0, "month": 0, "total": 0},
                "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd_eq": 0.0,
                "seconds": 0.0, "by_agent": {}, "by_channel": {}, "daily": {d: 0 for d in span}, "last_call_at": None}

    acc: dict[str, dict[str, Any]] = defaultdict(empty)
    for u in usage:
        lid = u.get("license_id") or "default"
        a = acc[lid]
        at = str(u.get("at") or "")
        try:
            when = datetime.fromisoformat(at)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age = (now - when).days
        t = _tokens(u)
        a["calls"]["total"] += 1
        a["seconds"] += float(u.get("duration_s") or 0)
        if when.date() == today:
            a["tokens"]["today"] += t
            a["calls"]["today"] += 1
        if age < 7:
            a["tokens"]["d7"] += t
        if age < 30:
            a["tokens"]["d30"] += t
        if at[:7] == month:
            a["tokens"]["month"] += t
            a["calls"]["month"] += 1
            a["input_tokens"] += int(u.get("input_tokens") or 0)
            a["output_tokens"] += int(u.get("output_tokens") or 0)
            a["cache_read_tokens"] += int(u.get("cache_read_tokens") or 0)
            a["cost_usd_eq"] += float(u.get("cost_usd_equivalent") or 0)
            agent = str(u.get("agent") or "?")
            a["by_agent"][agent] = a["by_agent"].get(agent, 0) + t
            ch = project_channel.get(str(u.get("project_id")), "?")
            a["by_channel"][ch] = a["by_channel"].get(ch, 0) + t
        day = when.date().isoformat()
        if day in a["daily"]:
            a["daily"][day] += t
        a["last_call_at"] = max(a["last_call_at"] or "", at) or None

    out = []
    for lic in licenses:
        a = acc.pop(lic.id, None) or empty()
        limit = lic.monthly_token_limit
        out.append({**lic.model_dump(), "limited_now": lic.limited_now(),
                    "status": "disabled" if not lic.enabled else "limited" if lic.limited_now() else "ok",
                    "usage_pct": round(100 * a["tokens"]["month"] / limit, 1) if limit else None,
                    **_finish(a)})
    default = acc.pop("default", None)
    totals = {"tokens_month": sum(x["tokens"]["month"] for x in out), "calls_month": sum(x["calls"]["month"] for x in out)}
    if default:
        totals["tokens_month"] += default["tokens"]["month"]
        totals["calls_month"] += default["calls"]["month"]
    return {"licenses": out, "default": _finish(default) if default else None, "totals": totals,
            "days": span, "generated_at": now.isoformat()}


def _finish(a: dict[str, Any]) -> dict[str, Any]:
    a = dict(a)
    a["daily"] = [{"day": d, "tokens": t} for d, t in a["daily"].items()]
    a["cost_usd_eq"] = round(a["cost_usd_eq"], 4)
    a["seconds"] = round(a["seconds"], 1)
    return a


def valid_license_id(lid: str) -> bool:
    return bool(_ID.match(lid))
