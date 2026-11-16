"""Agente 1 — Jefe / Orquestador (parte de agente).

El jefe toma decisiones deterministas para no gastar consumo de Claude en tareas que el
código resuelve de forma fiable: validar la petición, planificar el flujo, agrupar las
correcciones y redactar el informe final con datos reales.
"""
from __future__ import annotations

from collections import defaultdict

from ..core.models import CorrectionRequest
from ..orchestrator.pipeline import PIPELINE
from .base import Agent, AgentContext, AgentResult

MAX_CORRECTION_ROUNDS_DEFAULT = 2


def plan_invalidation(corrections: list[CorrectionRequest]) -> list[dict]:
    """Agrupa correcciones por fase destino → [{phase, scenes|None, reasons}] en orden del flujo."""
    grouped: dict[str, dict] = defaultdict(lambda: {"scenes": set(), "all": False, "reasons": []})
    for c in corrections:
        g = grouped[c.phase]
        g["reasons"].append(c.reason)
        if c.scene_index is None:
            g["all"] = True
        else:
            g["scenes"].add(c.scene_index)
    order = [p.id for p in PIPELINE]
    plan = []
    for phase in sorted(grouped, key=order.index):
        g = grouped[phase]
        plan.append({"phase": phase, "scenes": None if g["all"] else sorted(g["scenes"]), "reasons": g["reasons"]})
    return plan


class ChiefAgent(Agent):
    name = "chief"
    title = "Jefe / Orquestador"
    phases = frozenset({"intake", "project_setup", "corrections", "report"})

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        return getattr(self, f"_{phase}")(ctx)

    def _intake(self, ctx: AgentContext) -> AgentResult:
        spec = ctx.spec
        notes = []
        if spec.mode == "auto":
            notes.append("Modo automático: el director decidirá estilo, tono y música no indicados")
        if spec.budget_max_eur == 0:
            notes.append("Presupuesto 0 €: solo proveedores locales/gratuitos")
        ok, msg = ctx.llm.health_check()
        if not ok:
            notes.append(f"Aviso: motor Claude no disponible ({msg})")
        path = ctx.workspace.save("planning", "request", spec)
        return AgentResult(summary=f"Petición '{spec.name}' ({spec.duration_s}s, {spec.language}). " + "; ".join(notes),
                           artifacts={"request": str(path)})

    def _project_setup(self, ctx: AgentContext) -> AgentResult:
        plan = {
            "project_id": ctx.project_id,
            "phases": [{"n": p.number, "id": p.id, "title": p.title, "agent": p.agent, "kind": p.kind,
                        "depends_on": list(p.depends_on)} for p in PIPELINE],
            "platforms": [p.value for p in ctx.spec.platforms],
            "script_approval": "manual" if ctx.spec.require_script_approval else "automática",
        }
        path = ctx.workspace.save("planning", "production_plan", plan)
        return AgentResult(summary=f"Plan de producción con {len(PIPELINE)} fases", artifacts={"plan": str(path)})

    def _corrections(self, ctx: AgentContext) -> AgentResult:
        review = ctx.workspace.load("review", "latest")
        if review.get("passed"):
            return AgentResult(summary="Sin correcciones: la revisión es apta", metrics={"invalidate": []})
        corrections = [CorrectionRequest.model_validate(c) for c in review.get("corrections", [])]
        max_rounds = ctx.settings.get("max_correction_rounds", MAX_CORRECTION_ROUNDS_DEFAULT)
        rounds = ctx.settings.get("correction_rounds", 0)
        if rounds >= max_rounds or not corrections:
            return AgentResult(
                status="in_review",
                summary=f"Puntuación {review.get('score')} < umbral tras {rounds} rondas: requiere decisión humana",
                metrics={"invalidate": [], "needs_human": True},
            )
        plan = plan_invalidation(corrections)
        ctx.memory.add_decision(self.name, f"Ronda de correcciones {rounds + 1}: " +
                                ", ".join(f"{p['phase']}{p['scenes'] or ''}" for p in plan))
        return AgentResult(summary=f"Correcciones asignadas a {len(plan)} fases", metrics={"invalidate": plan})

    def _report(self, ctx: AgentContext) -> AgentResult:
        ws = ctx.workspace
        review = ws.load("review", "latest") if ws.has("review", "latest") else {}
        exports = ws.load("exports", "exports") if ws.has("exports", "exports") else {}
        published = ws.load("exports", "publish_results") if ws.has("exports", "publish_results") else {}
        usage = ctx.settings.get("llm_usage", [])
        costs = ctx.settings.get("costs", [])
        report = {
            "project_id": ctx.project_id,
            "request": ctx.spec.model_dump(mode="json"),
            "phase_summaries": ctx.memory.summaries(),
            "decisions": ctx.memory.decisions(),
            "quality": {"score": review.get("score"), "threshold": review.get("threshold"),
                        "passed": review.get("passed"), "disclaimer": review.get("disclaimer")},
            "exports": exports,
            "publication": published,
            "claude_usage": {
                "calls": len(usage),
                "total_duration_s": round(sum(u.get("duration_s") or 0 for u in usage), 1),
                "by_agent": _count_by(usage, "agent"),
                "note": "Indicador informativo; Claude Pro no factura por uso.",
            },
            "external_costs_eur": round(sum(c.get("amount_eur", 0) for c in costs), 4),
        }
        json_path = ws.save("reports", "report", report)
        md = _report_markdown(report)
        md_path = ws.dir("reports") / "report.md"
        md_path.write_text(md, encoding="utf-8")
        return AgentResult(summary=f"Informe final generado (calidad {report['quality']['score']})",
                           artifacts={"report": str(json_path), "report_md": str(md_path)})


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r.get(key, "?")] += 1
    return dict(out)


def _report_markdown(r: dict) -> str:
    lines = [f"# Informe de producción — {r['request']['name']}", "",
             f"- Tema: {r['request']['topic']}", f"- Duración objetivo: {r['request']['duration_s']} s",
             f"- Calidad interna: {r['quality']['score']} / 100 (umbral {r['quality']['threshold']}) — "
             f"{r['quality']['disclaimer'] or ''}",
             f"- Llamadas a Claude: {r['claude_usage']['calls']} ({r['claude_usage']['total_duration_s']} s)",
             f"- Costes externos: {r['external_costs_eur']} €", "", "## Fases", ""]
    lines += [f"- **{k}**: {v}" for k, v in r["phase_summaries"].items()]
    lines += ["", "## Exportaciones", ""]
    lines += [f"- {k}: `{v.get('path')}` ({v.get('duration_s')} s)" for k, v in r["exports"].items()]
    if r["publication"]:
        lines += ["", "## Publicación", ""]
        lines += [f"- {k}: {v.get('status')} {v.get('url') or ''} {v.get('message') or ''}" for k, v in r["publication"].items()]
    return "\n".join(lines) + "\n"
