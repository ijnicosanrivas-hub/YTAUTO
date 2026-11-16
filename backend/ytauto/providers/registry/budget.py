"""Control de presupuesto y registro de consumo de proveedores externos.

Límites aplicados antes de cada operación de pago:
- por proyecto (`ProjectSpec.budget_max_eur`),
- mensual global (ajuste `monthly_budget_eur`),
- mensual por proveedor (`provider_configs.monthly_budget_eur`),
- nº de generaciones por proyecto y proveedor (`max_generations_per_project`).
Se avisa al alcanzar el umbral (80 % por defecto) y se bloquea si se superaría el límite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from ...core.errors import BudgetExceeded
from ...core.models import utcnow
from ...db import schema as s

WARN_FRACTION_DEFAULT = 0.8


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class BudgetCheck(BaseModel):
    allowed: bool
    reason: str = ""
    warnings: list[str] = []


class BudgetManager:
    def __init__(self, engine: Engine, project_budget: Callable[[str], float | None] | None = None,
                 on_warning: Callable[[str, dict[str, Any]], None] | None = None,
                 month: Callable[[], str] = current_month):
        self.engine = engine
        self.project_budget = project_budget or (lambda pid: None)
        self.on_warning = on_warning or (lambda msg, data: None)
        self.month = month
        s.init_db(engine)

    # ------------------------------------------------------------------ ajustes globales
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.engine.connect() as c:
            row = c.execute(select(s.app_settings.c.value).where(s.app_settings.c.key == key)).first()
        return row[0] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        stmt = sqlite_insert(s.app_settings).values(key=key, value=value)
        with self.engine.begin() as c:
            c.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value}))

    @property
    def monthly_budget(self) -> float | None:
        v = self.get_setting("monthly_budget_eur")
        return float(v) if v is not None else None

    @property
    def warn_fraction(self) -> float:
        return float(self.get_setting("budget_warn_fraction", WARN_FRACTION_DEFAULT))

    # ------------------------------------------------------------------ consultas
    def _spent(self, **filters) -> float:
        q = select(func.coalesce(func.sum(func.coalesce(s.cost_ledger.c.actual_eur, s.cost_ledger.c.estimated_eur)), 0.0)
                   ).where(s.cost_ledger.c.status.in_(("reserved", "committed")))
        for k, v in filters.items():
            q = q.where(getattr(s.cost_ledger.c, k) == v)
        with self.engine.connect() as c:
            return float(c.execute(q).scalar_one())

    def _count(self, **filters) -> int:
        q = select(func.count()).select_from(s.cost_ledger).where(s.cost_ledger.c.status.in_(("reserved", "committed")))
        for k, v in filters.items():
            q = q.where(getattr(s.cost_ledger.c, k) == v)
        with self.engine.connect() as c:
            return int(c.execute(q).scalar_one())

    def spent_project(self, project_id: str) -> float:
        return self._spent(project_id=project_id)

    def spent_month(self, provider_id: str | None = None) -> float:
        return self._spent(month=self.month(), **({"provider_id": provider_id} if provider_id else {}))

    # ------------------------------------------------------------------ control
    def check(self, *, project_id: str | None, provider_id: str, amount: float,
              provider_monthly_budget: float | None, max_generations: int | None) -> BudgetCheck:
        warnings: list[str] = []
        limits: list[tuple[str, float | None, float]] = []
        if project_id:
            pb = self.project_budget(project_id)
            limits.append(("proyecto", pb if pb is not None else 0.0, self.spent_project(project_id)))
        limits.append(("mensual", self.monthly_budget, self.spent_month()))
        limits.append((f"proveedor {provider_id}", provider_monthly_budget, self.spent_month(provider_id)))
        for name, limit, spent in limits:
            if limit is None:
                continue
            if spent + amount > limit + 1e-9:
                return BudgetCheck(allowed=False, reason=(
                    f"Presupuesto {name} insuficiente: gastado {spent:.2f} €, operación {amount:.2f} €, "
                    f"límite {limit:.2f} €"))
            if limit > 0 and (spent + amount) >= limit * self.warn_fraction:
                warnings.append(f"Presupuesto {name} al {100 * (spent + amount) / limit:.0f} % ({spent + amount:.2f}/{limit:.2f} €)")
        if max_generations is not None and project_id:
            n = self._count(project_id=project_id, provider_id=provider_id)
            if n + 1 > max_generations:
                return BudgetCheck(allowed=False, reason=f"Límite de {max_generations} generaciones con {provider_id} alcanzado")
        for w in warnings:
            self.on_warning(w, {"project_id": project_id, "provider_id": provider_id})
        return BudgetCheck(allowed=True, warnings=warnings)

    def reserve(self, *, project_id: str | None, provider_id: str, category: str, operation: str,
                amount: float, scene_index: int | None) -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(s.cost_ledger).values(
                project_id=project_id, provider_id=provider_id, category=category, operation=operation,
                scene_index=scene_index, estimated_eur=amount, status="reserved", month=self.month(),
                at=utcnow().isoformat()))
            return int(res.inserted_primary_key[0])

    def commit(self, entry_id: int, actual: float | None) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.cost_ledger).where(s.cost_ledger.c.id == entry_id)
                      .values(status="committed", actual_eur=actual))

    def fail(self, entry_id: int) -> None:
        with self.engine.begin() as c:
            c.execute(update(s.cost_ledger).where(s.cost_ledger.c.id == entry_id).values(status="failed"))

    def require(self, check: BudgetCheck) -> None:
        if not check.allowed:
            raise BudgetExceeded(check.reason)

    def ledger(self, project_id: str | None = None) -> list[dict[str, Any]]:
        q = select(s.cost_ledger)
        if project_id:
            q = q.where(s.cost_ledger.c.project_id == project_id)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(s.cost_ledger.c.id)).mappings().all()
        return [dict(r) | {"amount_eur": r["actual_eur"] if r["actual_eur"] is not None else r["estimated_eur"]}
                for r in rows if r["status"] != "failed"]

    def summary(self) -> dict[str, Any]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.cost_ledger.c.provider_id, s.cost_ledger.c.month,
                                    func.count(), func.sum(func.coalesce(s.cost_ledger.c.actual_eur,
                                                                         s.cost_ledger.c.estimated_eur)))
                             .where(s.cost_ledger.c.status == "committed")
                             .group_by(s.cost_ledger.c.provider_id, s.cost_ledger.c.month)).all()
        return {
            "month": self.month(), "spent_month_eur": round(self.spent_month(), 4),
            "monthly_budget_eur": self.monthly_budget,
            "by_provider": [{"provider_id": p, "month": m, "operations": n, "eur": round(e or 0, 4)}
                            for p, m, n, e in rows],
        }
