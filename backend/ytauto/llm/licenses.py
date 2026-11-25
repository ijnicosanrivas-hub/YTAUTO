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
    budget_5h_tokens: int | None = None
    budget_week_tokens: int | None = None
    budget_month_usd: float | None = None
    observed_5h_tokens: int | None = None

    def limit_5h(self) -> int | None:
        """Límite de la ventana de 5 h: el que puso el usuario o, si no, el real observado al cortarla Claude."""
        return self.budget_5h_tokens or self.observed_5h_tokens

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
    budget_5h_tokens: int | None = Field(default=None, ge=0)
    budget_week_tokens: int | None = Field(default=None, ge=0)
    budget_month_usd: float | None = Field(default=None, ge=0)


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

    def set_limits(self, lid: str, budget_5h: int | None, budget_week: int | None, budget_usd: float | None) -> License:
        """Solo los límites de gasto (sin tocar la cuenta ni su clave). 0 o vacío = sin límite."""
        self.get(lid)
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid).values(
                budget_5h_tokens=budget_5h or None, budget_week_tokens=budget_week or None, budget_month_usd=budget_usd or None))
        return self.get(lid)

    def set_observed_5h(self, lid: str, tokens: int) -> None:
        """Consumo en la ventana de 5 h en el momento en que Claude cortó la licencia: su límite real."""
        if tokens > 0:
            with self.engine.begin() as c:
                c.execute(update(s.licenses).where(s.licenses.c.id == lid).values(observed_5h_tokens=int(tokens)))

    def touch(self, lid: str) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.licenses).where(s.licenses.c.id == lid).values(last_used_at=utcnow().isoformat()))

    def default_config_dir(self, lid: str) -> Path:
        return self.data_dir / "licencias" / lid

    # ------------------------------------------------------------------ conversión
    def _row(self, lid: str, d: LicenseInput, keep_secret: bool = False) -> dict[str, Any]:
        row: dict[str, Any] = {"id": lid, "name": d.name.strip(), "channel_id": d.channel_id, "kind": d.kind,
                               "plan": d.plan.strip(), "monthly_token_limit": d.monthly_token_limit,
                               "enabled": d.enabled, "notes": d.notes, "budget_5h_tokens": d.budget_5h_tokens or None,
                               "budget_week_tokens": d.budget_week_tokens or None, "budget_month_usd": d.budget_month_usd or None}
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


# ---------------------------------------------------------------------------- consumo en vivo

WINDOW_5H_S = 5 * 3600  # las suscripciones de Claude limitan por ventanas de 5 horas (y por semana)
WEEK_S = 7 * 86400
WARN_PCT = 80.0
SPARK_BUCKET_MIN, SPARK_BUCKETS = 5, 24  # últimas 2 horas, de 5 en 5 minutos


def _when(u: dict[str, Any]) -> datetime | None:
    try:
        w = datetime.fromisoformat(str(u.get("at") or ""))
    except ValueError:
        return None
    return w if w.tzinfo else w.replace(tzinfo=timezone.utc)


def call_tokens(u: dict[str, Any]) -> int:
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_tokens"))


def live_usage(lic: License | None, rows: list[dict[str, Any]], now: datetime | None = None, in_flight: int = 0) -> dict[str, Any]:
    """Consumo de una licencia AHORA: ventana de 5 h, semana, mes, ritmo, cuándo se libera y si debe frenarse.

    `rows` = llamadas de esa licencia (al menos de los últimos 7 días y del mes en curso). Los tokens salen de lo que
    Claude Code informa en cada llamada; las suscripciones no publican cuánto les queda, así que el «saldo» se mide
    contra el límite que pone el usuario o contra el límite real observado cuando Claude cortó la cuenta.
    """
    now = now or datetime.now(timezone.utc)
    t5, tw = now - timedelta(seconds=WINDOW_5H_S), now - timedelta(seconds=WEEK_S)
    month = now.strftime("%Y-%m")
    used_5h = used_week = used_month = 0
    usd_month = 0.0
    last15 = 0
    first_5h: datetime | None = None
    first_week: datetime | None = None
    spark = [0] * SPARK_BUCKETS
    recent: list[dict[str, Any]] = []
    for u in rows:
        w = _when(u)
        if w is None or w > now + timedelta(minutes=1):
            continue
        t = call_tokens(u)
        if w >= t5:
            used_5h += t
            first_5h = w if first_5h is None or w < first_5h else first_5h
        if w >= tw:
            used_week += t
            first_week = w if first_week is None or w < first_week else first_week
        if w.strftime("%Y-%m") == month:
            used_month += t
            usd_month += float(u.get("cost_usd_equivalent") or 0)
        age_min = (now - w).total_seconds() / 60
        if age_min <= 15:
            last15 += t
        b = int(age_min // SPARK_BUCKET_MIN)
        if 0 <= b < SPARK_BUCKETS:
            spark[SPARK_BUCKETS - 1 - b] += t
        recent.append({"at": w.isoformat(), "agent": u.get("agent"), "tokens": t})
    recent.sort(key=lambda r: r["at"], reverse=True)
    limit_5h = lic.limit_5h() if lic else None
    limit_week = lic.budget_week_tokens if lic else None
    limit_usd = lic.budget_month_usd if lic else None
    pct = lambda used, lim: round(100 * used / lim, 1) if lim else None  # noqa: E731
    pct_5h, pct_week = pct(used_5h, limit_5h), pct(used_week, limit_week)
    pct_usd = round(100 * usd_month / limit_usd, 1) if limit_usd else None
    burn = last15 / 15.0  # tokens por minuto (últimos 15 min)
    eta_min = round((limit_5h - used_5h) / burn, 1) if (limit_5h and burn > 0 and used_5h < limit_5h) else None
    frees_at = (first_5h + timedelta(seconds=WINDOW_5H_S)).isoformat() if first_5h else None
    brake: dict[str, Any] | None = None
    if limit_5h and used_5h >= limit_5h and first_5h:
        brake = {"reason": f"ventana de 5 h: {used_5h} de {limit_5h} tokens",
                 "until": (first_5h + timedelta(seconds=WINDOW_5H_S)).timestamp()}
    elif limit_week and used_week >= limit_week and first_week:
        brake = {"reason": f"semana: {used_week} de {limit_week} tokens",
                 "until": (first_week + timedelta(seconds=WEEK_S)).timestamp()}
    elif limit_usd and usd_month >= limit_usd:
        nxt = (now.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        brake = {"reason": f"gasto del mes: {usd_month:.2f} $ de {limit_usd:.2f} $", "until": nxt.timestamp()}
    limited = bool(lic and lic.limited_now(now.timestamp()))
    worst = max([p for p in (pct_5h, pct_week, pct_usd) if p is not None], default=None)
    if lic and not lic.enabled:
        status = "inactiva"
    elif limited:
        status = "agotada"
    elif brake:
        status = "freno"
    elif worst is not None and worst >= WARN_PCT:
        status = "aviso"
    else:
        status = "ok"
    return {
        "used_5h": used_5h, "used_week": used_week, "used_month": used_month, "usd_month": round(usd_month, 4),
        "limit_5h": limit_5h, "limit_5h_source": ("tuyo" if lic and lic.budget_5h_tokens else "observado" if limit_5h else None),
        "limit_week": limit_week, "limit_usd": limit_usd,
        "pct_5h": pct_5h, "pct_week": pct_week, "pct_usd": pct_usd,
        "remaining_5h": max(0, limit_5h - used_5h) if limit_5h else None,
        "burn_per_min": round(burn, 1), "eta_min": eta_min, "window_frees_at": frees_at,
        "brake": brake, "status": status, "in_flight": in_flight,
        "limited_until": lic.limited_until if lic else None, "limited_reason": lic.limited_reason if lic else None,
        "spark": spark, "recent": recent[:6], "calls_5h": sum(1 for u in rows if (_when(u) or now) >= t5),
    }


# ---------------------------------------------------------------------------- enrutado

ProviderFactory = Callable[[License, "str | None"], LLMProvider]


class LicenseRouter(LLMProvider):
    """Atiende cada llamada con la licencia asignada al agente en ese proyecto (o la del canal)."""

    name = "licencias"

    def __init__(self, store: LicenseStore, default: LLMProvider, factory: ProviderFactory,
                 spec_lookup: Callable[[str], ProjectSpec],
                 usage_rows: Callable[[str | None, datetime], list[dict[str, Any]]] | None = None,
                 on_event: Callable[[dict[str, Any]], None] | None = None):
        """`usage_rows(licencia, desde)` = llamadas registradas de esa licencia (para el freno de gasto);
        `on_event` = aviso en vivo de cada llamada que empieza o termina (para el monitor)."""
        self.usage_rows = usage_rows
        self.on_event = on_event
        self.in_flight: dict[str, int] = defaultdict(int)
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

    def live(self, lic: License | None, now: datetime | None = None) -> dict[str, Any]:
        """Consumo en vivo de una licencia (None = la sesión principal)."""
        now = now or datetime.now(timezone.utc)
        since = min(now - timedelta(seconds=WEEK_S), now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        rows = self.usage_rows(lic.id if lic else None, since) if self.usage_rows else []
        return live_usage(lic, rows, now, self.in_flight[lic.id if lic else "default"])

    def _emit(self, lic: License | None, phase: str, **extra: Any) -> None:
        if self.on_event:
            try:
                self.on_event({"license_id": lic.id if lic else None, "phase": phase,
                               "in_flight": self.in_flight[lic.id if lic else "default"], **extra})
            except Exception:  # noqa: BLE001 - el monitor nunca debe romper una llamada
                pass

    def _complete_with(self, lic: License | None, request: LLMRequest) -> LLMResponse:
        key = lic.id if lic else "default"
        if lic is not None:
            if lic.is_limited and not lic.limited_now():
                self.store.clear_limit(lic.id)  # ya pasó la hora de reinicio
                lic = self.store.get(lic.id)
            if lic.limited_now():
                raise UsageLimitError(f"La licencia «{lic.name}» está agotada: {lic.limited_reason or 'límite de uso'}",
                                      resets_at=str(int(lic.limited_until)) if lic.limited_until else None,
                                      license_id=lic.id)
            brake = self.live(lic)["brake"] if self.usage_rows else None
            if brake:  # freno de gasto: se para ANTES de gastar más de lo que el usuario permitió
                reason = f"Freno de gasto ({brake['reason']})"
                self.store.mark_limited(lic.id, str(int(brake["until"])), reason)
                self._emit(lic, "brake", reason=reason)
                raise UsageLimitError(f"La licencia «{lic.name}» ha llegado a su límite: {brake['reason']}",
                                      resets_at=str(int(brake["until"])), license_id=lic.id)
        provider = self._provider(lic) if lic is not None else self.default
        with self._locks[key]:  # nunca dos llamadas simultáneas con la misma cuenta (ni con la sesión principal)
            self.in_flight[key] += 1
            self._emit(lic, "start", agent=request.agent)
            try:
                response = provider.complete(request)
            except UsageLimitError as e:
                if lic is not None:
                    e.license_id = lic.id
                    if self.usage_rows:  # lo gastado en la ventana al cortarla Claude = su límite real
                        self.store.set_observed_5h(lic.id, self.live(lic)["used_5h"])
                    self.store.mark_limited(lic.id, e.resets_at, str(e))
                raise
            finally:
                self.in_flight[key] -= 1
        if lic is not None:
            response.usage.license_id = lic.id
            self.store.touch(lic.id)
        self._emit(lic, "end", agent=request.agent, tokens=call_tokens(response.usage.model_dump()))
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
