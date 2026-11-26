"""Pruebas del orquestador: flujo completo, aprobaciones, límites, reanudación y correcciones."""
from __future__ import annotations

from ytauto.core.models import PhaseStatus, ProjectSpec, ProjectStatus
from ytauto.llm.base import AuthenticationError, UsageLimitError
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM
from ytauto.orchestrator.pipeline import PIPELINE, downstream


def statuses(orch, pid):
    return {r.phase: r.status for r in orch.store.list_phases(pid)}


def test_pipeline_has_20_ordered_phases():
    assert [p.number for p in PIPELINE] == list(range(1, 21))
    assert "report" in downstream("script")
    assert "creative_direction" not in downstream("script")


def test_full_flow_with_approvals(make_orchestrator, spec, mock_providers):
    orch = make_orchestrator()
    pid = orch.create_project(spec)
    r = orch.run(pid)
    assert r.outcome == "waiting_approval" and r.phase == "script_approval"
    orch.approve(pid, "script_approval")
    r = orch.run(pid)
    assert r.outcome == "waiting_approval" and r.phase == "final_approval"
    orch.approve(pid, "final_approval")
    r = orch.run(pid)
    assert r.outcome == "waiting_approval" and r.phase == "publish"
    orch.approve(pid, "publish:youtube_shorts")
    r = orch.run(pid)
    assert r.outcome == "completed"
    st = statuses(orch, pid)
    assert all(s.is_done for s in st.values())
    pub = next(p for k, p in mock_providers.items() if k.value == "publishing")
    assert [p.platform for p in pub.published] == ["youtube_shorts"]
    report = orch.store.get_project(pid)
    assert report.status is ProjectStatus.COMPLETED


def test_auto_mode_skips_script_approval_but_not_final(make_orchestrator):
    orch = make_orchestrator()
    pid = orch.create_project(ProjectSpec(name="a", topic="el sol", duration_s=45, require_script_approval=False))
    r = orch.run(pid)
    assert r.phase == "final_approval"


def test_manual_publication_decision_completes_without_publishing(make_orchestrator, spec, mock_providers):
    orch = make_orchestrator()
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    orch.approve(pid, "final_approval")
    orch.run(pid)
    orch.approve(pid, "publish_decision", note="Publicaré manualmente")
    assert orch.run(pid).outcome == "completed"
    pub = next(p for k, p in mock_providers.items() if k.value == "publishing")
    assert pub.published == []


def test_usage_limit_blocks_and_resume_continues(make_orchestrator, spec):
    draft = LocalDraftLLM()
    calls = {"n": 0}

    def director(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return UsageLimitError("Claude AI usage limit reached|resets 5pm")
        return draft.complete(req).data

    orch = make_orchestrator(llm=ScriptedLLM({"director": director}, fallback=draft))
    pid = orch.create_project(spec)
    r = orch.run(pid)
    assert r.outcome == "usage_limit" and r.phase == "creative_direction"
    assert orch.store.get_project(pid).status is ProjectStatus.BLOCKED
    assert orch.step(pid).outcome == "blocked"  # no lanza más tareas
    orch.resume(pid)
    r = orch.run(pid)
    assert r.phase == "script_approval"
    # Las fases anteriores no se repiten
    assert orch.store.get_phase(pid, "intake").attempts == 1


def test_auth_error_blocks_project(make_orchestrator, spec):
    orch = make_orchestrator(llm=ScriptedLLM({"director": [AuthenticationError("Please run /login")]},
                                             fallback=LocalDraftLLM()))
    pid = orch.create_project(spec)
    r = orch.run(pid)
    assert r.outcome == "auth_error"
    assert "login" in (orch.store.get_project(pid).blocked_reason or "")


def test_resume_after_crash_does_not_repeat_completed_phases(make_orchestrator, spec, store_factory):
    store = store_factory()
    orch = make_orchestrator(store=store)
    pid = orch.create_project(spec)
    orch.run(pid)  # hasta aprobación del guion
    # Simula caída a mitad de 'voice'
    orch.approve(pid, "script_approval")
    orch.step(pid)  # scene_prep
    rec = store.get_phase(pid, "resource_generation")
    rec.status = PhaseStatus.RUNNING
    store.save_phase(rec)
    # Nuevo proceso (nuevo orquestador, mismo almacén)
    orch2 = make_orchestrator(store=store)
    orch2.resume(pid)
    assert store.get_phase(pid, "resource_generation").status is PhaseStatus.PENDING
    r = orch2.run(pid)
    assert r.phase == "final_approval"
    assert store.get_phase(pid, "script").attempts == 1


def test_pause_and_cancel(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = orch.create_project(spec)
    orch.pause(pid)
    assert orch.step(pid).outcome == "paused"
    orch.resume(pid)
    orch.step(pid)
    orch.cancel(pid)
    assert orch.step(pid).outcome == "cancelled"


def test_review_corrections_loop_reruns_only_target(make_orchestrator, spec):
    draft = LocalDraftLLM()
    reviews = {"n": 0}

    def reviewer(req):
        reviews["n"] += 1
        if reviews["n"] == 1:
            return {"scores": {"hook": 2, "pacing": 5, "coherence": 5, "spelling": 5, "legibility": 5},
                    "issues": [{"target_agent": "resources", "scene_index": 3, "reason": "Imagen poco clara",
                                "severity": "major"}], "summary": "mejorable"}
        return draft.complete(req).data

    orch = make_orchestrator(llm=ScriptedLLM({"reviewer": reviewer}, fallback=draft), review_threshold=80)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    r = orch.run(pid)
    assert r.phase == "final_approval"
    assert reviews["n"] == 2
    assert orch.store.get_phase(pid, "resource_generation").attempts == 2
    assert orch.store.get_phase(pid, "script").attempts == 1  # el guion no se rehízo
    edit = orch.store.get_phase(pid, "edit")
    assert edit.result["metrics"]["rendered"] == 1  # solo la escena 3


def test_correction_rounds_are_bounded(make_orchestrator, spec):
    always_bad = {"scores": {"hook": 1, "pacing": 1, "coherence": 1, "spelling": 1, "legibility": 1},
                  "issues": [{"target_agent": "editor", "reason": "mal", "severity": "major"}], "summary": "x"}
    orch = make_orchestrator(llm=ScriptedLLM({"reviewer": lambda r: always_bad}, fallback=LocalDraftLLM()),
                             max_correction_rounds=2)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    r = orch.run(pid)
    assert r.phase == "final_approval"  # tras 2 rondas pasa a decisión humana
    assert orch.store.get_project(pid).correction_rounds == 2
    assert orch.store.get_phase(pid, "review").attempts == 3


def test_script_rejection_rewrites_script(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = orch.create_project(spec)
    orch.run(pid)
    orch.approve(pid, "script_approval", approved=False, note="Más humor")
    assert orch.store.get_phase(pid, "script").status is PhaseStatus.PENDING
    r = orch.run(pid)
    assert r.phase == "script_approval"
    assert orch.store.get_phase(pid, "script").attempts == 2
    script_req = orch.store.get_phase(pid, "script")
    assert script_req.status is PhaseStatus.COMPLETED


def test_redo_single_scene(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    orch.redo_scenes(pid, [0], reason="Quiero otra imagen para el gancho")
    r = orch.run(pid)
    assert r.phase == "final_approval"
    assert orch.store.get_phase(pid, "edit").result["metrics"]["rendered"] == 1


def test_events_reflect_real_activity(make_orchestrator, spec):
    orch = make_orchestrator()
    seen = []
    orch.events.subscribe(lambda e: seen.append(e.type))
    pid = orch.create_project(spec)
    orch.run(pid)
    assert "agent.started" in seen and "agent.finished" in seen and "llm.call" in seen
    assert "phase.status" in seen


def test_llm_usage_is_recorded(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = orch.create_project(spec)
    orch.run(pid)
    agents = {u["agent"] for u in orch.store.llm_usage(pid)}
    assert {"director", "scriptwriter"} <= agents


def test_cannot_approve_gate_before_it_is_reached(make_orchestrator, spec):
    import pytest
    orch = make_orchestrator()
    pid = orch.create_project(spec)
    with pytest.raises(ValueError):
        orch.approve(pid, "final_approval")
    with pytest.raises(ValueError):
        orch.approve(pid, "publish:tiktok")
    orch.run(pid)
    orch.approve(pid, "script_approval")  # ahora sí está pendiente


def test_script_rejection_comment_actually_reaches_the_scriptwriter(make_orchestrator, spec):
    """Hallado al revisar la fase 10: el comentario del usuario al rechazar el guion no llegaba a Claude
    (solo se enviaban las correcciones por escenas), así que el guion se regeneraba a ciegas."""
    draft = LocalDraftLLM()
    scripts = []

    def scriptwriter(req):
        scripts.append(req)
        return draft.complete(req).data

    orch = make_orchestrator(llm=ScriptedLLM({"scriptwriter": scriptwriter}, fallback=draft))
    pid = orch.create_project(spec)
    orch.run(pid)
    assert scripts[0].context.get("corrections") in (None, [])  # primera vez: sin correcciones
    orch.approve(pid, "script_approval", approved=False, note="Más humor y menos datos técnicos")
    orch.run(pid)
    second = scripts[1].context
    assert any("Más humor" in c["reason"] for c in second["corrections"])
    assert second["previous_script"]["scenes"]  # y ve el guion anterior para mejorarlo, no empezar de cero
    assert "corrections" in scripts[1].task.lower() or "correc" in scripts[1].task.lower()


# ---------------------------------------------------------------- mejora automática de incidencias graves (nota apta)
GOOD = {"hook": 9, "pacing": 9, "coherence": 9, "spelling": 10, "legibility": 9}


def reviewer_with(issues_per_call):
    """Revisor simulado: devuelve las incidencias de cada llamada (la última se repite) con una nota apta."""
    calls = {"n": 0}

    def handler(req):
        issues = issues_per_call[min(calls["n"], len(issues_per_call) - 1)]
        calls["n"] += 1
        return {"scores": GOOD, "issues": issues, "summary": "ok"}

    return handler, calls


def issue(agent, scene, severity="major", reason="Mejorable"):
    return {"target_agent": agent, "scene_index": scene, "reason": reason, "severity": severity}


def auto_orch(make_orchestrator, handler, **kw):
    draft = LocalDraftLLM()
    return make_orchestrator(llm=ScriptedLLM({"reviewer": handler}, fallback=draft), **kw)


def test_passed_review_with_major_resource_issue_gets_exactly_one_improvement_round(make_orchestrator, spec):
    handler, calls = reviewer_with([[issue("resources", 3, reason="Imagen poco clara")], [issue("resources", 3)]])
    orch = auto_orch(make_orchestrator, handler)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    r = orch.run(pid)
    assert r.phase == "final_approval"
    assert calls["n"] == 2  # revisó, mejoró una vez y volvió a revisar; la segunda vez NO insiste
    assert orch.store.get_project(pid).correction_rounds == 1
    assert orch.store.get_phase(pid, "script").attempts == 1  # el guion no se tocó
    assert orch.store.get_phase(pid, "resource_generation").attempts == 2
    assert orch.store.get_phase(pid, "edit").result["metrics"]["rendered"] == 1  # solo la escena 3


def test_major_script_issue_rewrites_the_script_when_the_user_did_not_need_to_approve_it(make_orchestrator, spec):
    handler, calls = reviewer_with([[issue("scriptwriter", 2, reason="La escena 2 se adelanta a la revelación")], []])
    seen = []
    draft = LocalDraftLLM()

    def scriptwriter(req):
        seen.append(req)
        return draft.complete(req).data

    orch = make_orchestrator(llm=ScriptedLLM({"reviewer": handler, "scriptwriter": scriptwriter}, fallback=draft))
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    assert orch.store.get_phase(pid, "script").attempts == 2 and calls["n"] == 2
    assert any("se adelanta a la revelación" in c["reason"] for c in seen[1].context["corrections"])  # Claude lo ve


def test_script_approved_by_the_user_is_never_rewritten_silently(make_orchestrator, spec):
    handler, calls = reviewer_with([[issue("scriptwriter", 2), issue("resources", 4)], []])
    orch = auto_orch(make_orchestrator, handler)
    pid = orch.create_project(spec)  # require_script_approval=True
    orch.run(pid)
    orch.approve(pid, "script_approval")
    orch.run(pid)
    assert orch.store.get_phase(pid, "script").attempts == 1  # su guion aprobado se respeta
    assert orch.store.get_phase(pid, "resource_generation").attempts == 2  # lo visual sí se mejora
    from ytauto.core.workspace import ProjectMemory, Workspace
    decisions = [d["decision"] for d in ProjectMemory(Workspace(orch.settings.projects_dir, pid)).decisions()]
    assert any("lo aprobaste tú" in d for d in decisions)  # queda constancia de por qué no se tocó el guion


def test_only_content_agents_and_only_major_issues_are_applied(make_orchestrator, spec):
    handler, calls = reviewer_with([[issue("sound", None), issue("editor", 1), issue("resources", 2, "minor"),
                                     issue("scriptwriter", 1, "minor"), issue("director", None)]])
    orch = auto_orch(make_orchestrator, handler)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    assert calls["n"] == 1 and orch.store.get_project(pid).correction_rounds == 0  # nada que aplicar automáticamente


def test_automatic_improvement_can_be_disabled(make_orchestrator, spec):
    handler, calls = reviewer_with([[issue("resources", 3)]])
    orch = auto_orch(make_orchestrator, handler, fix_major_when_passed=False)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    assert calls["n"] == 1 and orch.store.get_phase(pid, "resource_generation").attempts == 1


def test_improvement_is_skipped_if_a_correction_round_was_already_used(make_orchestrator, spec):
    """Una nota NO apta ya gastó la ronda: la mejora de una nota apta no se acumula encima."""
    bad = {"scores": {"hook": 1, "pacing": 1, "coherence": 1, "spelling": 1, "legibility": 1},
           "issues": [issue("editor", None)], "summary": "mal"}
    good_with_issue = {"scores": GOOD, "issues": [issue("resources", 3)], "summary": "ok"}
    seq = [bad, good_with_issue]
    calls = {"n": 0}

    def handler(req):
        out = seq[min(calls["n"], 1)]
        calls["n"] += 1
        return out

    orch = auto_orch(make_orchestrator, handler)
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    assert calls["n"] == 2 and orch.store.get_project(pid).correction_rounds == 1
