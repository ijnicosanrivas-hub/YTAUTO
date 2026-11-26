"""Motor de vídeos virales: estrategia del director, guion con retención y decisiones del usuario antes de gastar."""
from __future__ import annotations

from ytauto.agents.briefing import BASE_QUESTIONS
from ytauto.agents.director import check_viral
from ytauto.agents.scriptwriter import SLOW_OPENING
from ytauto.core.models import CreativeBrief, ProjectSpec, Script
from ytauto.core.workspace import Workspace
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM
from ytauto.orchestrator.pipeline import OPTIONAL_GATES, PHASES

from test_agents import PIPE, run_until

GATED = dict(require_concept_approval=True, require_script_approval=True, require_storyboard_approval=True)


def draft_brief(make_ctx) -> CreativeBrief:
    ctx = make_ctx()
    run_until(ctx, "creative_direction")
    return ctx.workspace.load("planning", "creative_brief", CreativeBrief)


# ------------------------------------------------------------------ estrategia del director
def test_director_delivers_a_complete_viral_strategy(make_ctx):
    b = draft_brief(make_ctx)
    assert len(b.hook_options) == 3 and len({h.style for h in b.hook_options}) == 3
    assert b.viral_angle and b.cta and len(b.title_options) == 3 and b.cover_concept and b.opening_scene
    assert len(b.retention_plan) >= 3 and b.hook() is b.hook_options[b.chosen_hook]
    assert check_viral(b, 60, hook_max_words=8) == []


def test_viral_criteria_reject_weak_plans(make_ctx):
    b = draft_brief(make_ctx)
    weak = b.model_copy(deep=True)
    weak.hook_options = weak.hook_options[:1]
    weak.viral_angle, weak.cta, weak.cover_concept, weak.title_options = "", "", "", ["uno"]
    weak.retention_plan = [r.model_copy(update={"at_s": 50}) for r in weak.retention_plan]
    issues = " | ".join(check_viral(weak, 60, hook_max_words=8))
    for needle in ("3 ganchos", "viral_angle", "cta", "title_options", "cover_concept", "primer 40 %"):
        assert needle in issues, needle
    same = b.model_copy(deep=True)
    for h in same.hook_options:
        h.style = "pregunta"
    same.hook_options[0].text = " ".join(["palabra"] * 30)
    same.hook_options[1].on_screen_text = "uno dos tres cuatro cinco seis siete"
    issues = " | ".join(check_viral(same, 60, hook_max_words=8))
    assert "tipos distintos" in issues and "30 palabras" in issues and "6 palabras" in issues


def test_director_gets_the_users_notes_when_the_concept_is_rejected(make_ctx):
    from ytauto.core.models import CorrectionRequest
    seen = {}

    def director(req):
        seen.update(req.context)
        return LocalDraftLLM()._director(req.context)
    ctx = make_ctx(llm=ScriptedLLM({"director": director}), corrections=[
        CorrectionRequest(target_agent="director", phase="creative_direction", reason="Más misterio, menos datos")])
    run_until(ctx, "creative_direction")
    assert seen["corrections"][0]["reason"] == "Más misterio, menos datos"
    assert seen["channel"]["id"] == "general"


# ------------------------------------------------------------------ guion
def test_script_uses_the_cta_and_never_opens_slowly(make_ctx):
    ctx = make_ctx()
    run_until(ctx, *PIPE[:2])
    s = ctx.workspace.load("scripts", "script", Script)
    assert s.call_to_action and s.retention_beats
    for slow in ("Hola a todos, hoy", "Bienvenidos al canal", "En este vídeo te cuento", "hey, ¿qué tal?"):
        assert SLOW_OPENING.search(slow), slow
    for fine in ("¿Sabías que los pulpos tienen tres corazones?", "Holanda esconde un secreto"):
        assert not SLOW_OPENING.search(fine), fine


# ------------------------------------------------------------------ decisiones antes de gastar
def test_new_gates_sit_before_the_expensive_steps():
    assert PHASES["script"].depends_on == ("concept_approval",)
    assert PHASES["resource_generation"].depends_on == ("storyboard_approval",)
    assert set(OPTIONAL_GATES) == {"concept_approval", "script_approval", "storyboard_approval"}


def test_user_picks_the_hook_and_edits_the_storyboard_before_any_generation(make_orchestrator, spec, mock_providers):
    orch = make_orchestrator()
    pid = orch.create_project(spec.model_copy(update=GATED))
    r = orch.run(pid)
    assert (r.outcome, r.phase) == ("waiting_approval", "concept_approval")
    ws = Workspace(orch.settings.projects_dir, pid)
    assert not ws.has("scripts", "script")  # el guion no se escribe hasta decidir el concepto
    orch.approve(pid, "concept_approval", note="Tono más misterioso", data={"chosen_hook": 2})
    brief = ws.load("planning", "creative_brief", CreativeBrief)
    assert brief.chosen_hook == 2 and brief.user_notes == "Tono más misterioso"
    assert orch.run(pid).phase == "script_approval"
    orch.approve(pid, "script_approval")
    r = orch.run(pid)
    assert (r.outcome, r.phase) == ("waiting_approval", "storyboard_approval")
    assert not ws.has("resources", "assets")  # nada generado (ni un crédito) antes de aprobar el storyboard
    orch.approve(pid, "storyboard_approval", data={"prompts": {"0": "Pulpo gigante saliendo de la oscuridad"},
                                                   "kinds": {"1": "video"}})
    prompts = ws.load("resources", "prompts")["prompts"]
    assert prompts[0]["prompt"] == "Pulpo gigante saliendo de la oscuridad" and prompts[1]["kind"] == "video"
    assert orch.run(pid).phase == "final_approval"
    image = next(p for k, p in mock_providers.items() if k.value == "image")
    assert any("Pulpo gigante saliendo de la oscuridad" in (q.prompt or "") for q in getattr(image, "requests", [])) \
        or ws.load("resources", "assets")["0"]["prompt"].startswith("Pulpo gigante")


def test_rejecting_the_concept_or_storyboard_redoes_only_that_step(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = orch.create_project(spec.model_copy(update=GATED))
    orch.run(pid)
    orch.approve(pid, "concept_approval", approved=False, note="Quiero un enfoque de mito vs realidad")
    rec = orch.store.get_phase(pid, "creative_direction")
    assert rec.status.value == "pending" and "mito vs realidad" in rec.corrections[0].reason
    assert orch.run(pid).phase == "concept_approval"  # el director lo rehace y vuelve a preguntar
    orch.approve(pid, "concept_approval")
    orch.run(pid)
    orch.approve(pid, "script_approval")
    assert orch.run(pid).phase == "storyboard_approval"
    orch.approve(pid, "storyboard_approval", approved=False, note="Menos clips, más ilustración")
    assert orch.store.get_phase(pid, "scene_prep").status.value == "pending"
    assert orch.store.get_phase(pid, "script_approval").status.value == "approved"  # el guion no se toca
    assert orch.run(pid).phase == "storyboard_approval"


def test_invalid_hook_choice_is_refused(make_orchestrator, spec):
    import pytest
    orch = make_orchestrator()
    pid = orch.create_project(spec.model_copy(update=GATED))
    orch.run(pid)
    with pytest.raises(ValueError):
        orch.approve(pid, "concept_approval", data={"chosen_hook": 9})


def test_auto_mode_and_old_projects_keep_their_flow(make_orchestrator, tmp_path):
    orch = make_orchestrator()
    pid = orch.create_project(ProjectSpec(name="a", topic="el sol", duration_s=45, require_script_approval=False))
    assert orch.run(pid).phase == "final_approval"  # sin las puertas nuevas: todo seguido como antes
    # Proyecto creado con la versión anterior (sin las fases nuevas): se completan como ya aprobadas.
    from sqlalchemy import delete
    from ytauto.db import schema as s
    from ytauto.db.schema import make_engine
    from ytauto.db.store import SqlStateStore
    from ytauto.orchestrator.orchestrator import Orchestrator, OrchestratorSettings
    store = SqlStateStore(make_engine(tmp_path / "viejo.db"))
    old = Orchestrator(store=store, llm=LocalDraftLLM(), providers=orch.providers,
                       settings=OrchestratorSettings(projects_dir=tmp_path / "p2"))
    pid2 = old.create_project(ProjectSpec(name="b", topic="la luna", duration_s=45))
    with store.engine.begin() as c:
        c.execute(delete(s.phases).where(s.phases.c.phase.in_(["concept_approval", "storyboard_approval"])))
    assert len(store.list_phases(pid2)) == 18
    assert old.run(pid2).phase == "script_approval"
    assert store.get_phase(pid2, "concept_approval").status.value == "approved"


# ------------------------------------------------------------------ entrevista previa
def test_the_interview_covers_design_and_structure():
    ids = [q.id for q in BASE_QUESTIONS]
    for must in ("duration", "quality", "hook_style", "structure", "visual_style", "references", "ending"):
        assert must in ids, must
