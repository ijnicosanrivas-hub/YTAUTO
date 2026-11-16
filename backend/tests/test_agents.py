"""Pruebas unitarias de los nueve agentes (sin Claude real ni costes)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ytauto.agents.chief import ChiefAgent, plan_invalidation
from ytauto.agents.director import DirectorAgent, check_brief
from ytauto.agents.editor import EditorAgent
from ytauto.agents.publisher import PublisherAgent
from ytauto.agents.resources import ResourcesAgent
from ytauto.agents.reviewer import ReviewerAgent
from ytauto.agents.scriptwriter import ScriptwriterAgent
from ytauto.agents.sound import SoundAgent
from ytauto.agents.voice import VoiceAgent, normalize_for_tts
from ytauto.core.errors import AcceptanceError
from ytauto.core.models import CorrectionRequest, CreativeBrief, MediaAsset, Script
from ytauto.core.timeline import EditManifest, VoiceManifest
from ytauto.llm.mock import LocalDraftLLM, ScriptedLLM


def run_until(ctx, *phases):
    agents = {"creative_direction": DirectorAgent(), "script": ScriptwriterAgent(), "scene_prep": ResourcesAgent(),
              "resource_generation": ResourcesAgent(), "voice": VoiceAgent(), "edit": EditorAgent(),
              "sound": SoundAgent(), "render": EditorAgent(), "review": ReviewerAgent(),
              "exports": PublisherAgent(), "publish_prep": PublisherAgent()}
    out = None
    for p in phases:
        out = agents[p].run(p, ctx)
    return out


PIPE = ["creative_direction", "script", "scene_prep", "resource_generation", "voice", "edit", "sound", "render"]


# ---------------------------------------------------------------- 1. Jefe
def test_chief_intake_and_setup(make_ctx):
    ctx = make_ctx()
    r = ChiefAgent().run("intake", ctx)
    assert "Prueba" in r.summary
    r = ChiefAgent().run("project_setup", ctx)
    plan = ctx.workspace.load("planning", "production_plan")
    assert len(plan["phases"]) == 18


def test_chief_plan_invalidation_groups_by_phase():
    plan = plan_invalidation([
        CorrectionRequest(target_agent="voice", phase="voice", scene_index=2, reason="a"),
        CorrectionRequest(target_agent="scriptwriter", phase="script", scene_index=1, reason="b"),
        CorrectionRequest(target_agent="scriptwriter", phase="script", scene_index=3, reason="c"),
    ])
    assert [p["phase"] for p in plan] == ["script", "voice"]
    assert plan[0]["scenes"] == [1, 3]


def test_chief_corrections_needs_human_after_max_rounds(make_ctx):
    ctx = make_ctx(settings={"max_correction_rounds": 2, "correction_rounds": 2})
    ctx.workspace.save("review", "latest", {"passed": False, "score": 50, "corrections": [
        {"target_agent": "editor", "phase": "edit", "reason": "x"}]})
    r = ChiefAgent().run("corrections", ctx)
    assert r.metrics["needs_human"] is True


# ---------------------------------------------------------------- 2. Director
def test_director_produces_valid_brief(make_ctx):
    ctx = make_ctx()
    DirectorAgent().run("creative_direction", ctx)
    brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
    assert abs(sum(s.duration_s for s in brief.scenes) - 60) < 0.01
    assert brief.scenes[0].section.value == "hook" and brief.scenes[0].duration_s <= 3
    assert check_brief(brief, 60, 3.0) == []


def test_director_retries_with_feedback_then_accepts(make_ctx):
    good = LocalDraftLLM()
    bad = {"concept": "x", "tone": "x", "visual_style": "x", "pacing": "x", "target_duration_s": 60,
           "music_direction": "x", "scenes": []}
    llm = ScriptedLLM({"director": lambda req: bad if not req.feedback else good.complete(req).data})
    ctx = make_ctx(llm=llm)
    DirectorAgent().run("creative_direction", ctx)
    assert len(llm.calls) == 2 and llm.calls[1].feedback  # el segundo intento recibe los fallos


def test_director_fails_after_max_attempts(make_ctx):
    bad = {"concept": "x", "tone": "x", "visual_style": "x", "pacing": "x", "target_duration_s": 60,
           "music_direction": "x", "scenes": []}
    ctx = make_ctx(llm=ScriptedLLM({"director": [bad, bad]}))
    with pytest.raises(AcceptanceError):
        DirectorAgent().run("creative_direction", ctx)


# ---------------------------------------------------------------- 3. Guionista
def test_scriptwriter_fits_duration(make_ctx):
    ctx = make_ctx()
    run_until(ctx, "creative_direction", "script")
    script = ctx.workspace.load("scripts", "script", Script)
    est = sum(ctx.narrative.estimate_speech_s(s.narration, "es") for s in script.scenes)
    assert est <= 60 * 1.05
    assert script.hook and script.closing
    assert all(s.subtitle_lines for s in script.scenes if s.narration)


def test_scriptwriter_rejects_text_too_long(make_ctx):
    draft = LocalDraftLLM()

    def too_long(req):
        data = draft.complete(req).data
        data["scenes"][2]["narration"] = " ".join(["palabra"] * 200)
        return data

    ctx = make_ctx(llm=ScriptedLLM({"director": draft.complete and (lambda r: draft.complete(r).data),
                                    "scriptwriter": too_long}))
    DirectorAgent().run("creative_direction", ctx)
    with pytest.raises(AcceptanceError) as e:
        ScriptwriterAgent().run("script", ctx)
    assert "acorta el texto" in str(e.value)


# ---------------------------------------------------------------- 4. Recursos
def test_resources_one_asset_per_scene_with_license(make_ctx):
    ctx = make_ctx()
    run_until(ctx, "creative_direction", "script", "scene_prep", "resource_generation")
    assets = ctx.workspace.load("resources", "assets")
    brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
    assert len(assets) == len(brief.scenes)
    hashes = [a["perceptual_hash"] for a in assets.values()]
    assert len(set(hashes)) == len(hashes)  # sin repetidas
    assert all(a["license"]["name"] != "unknown" for a in assets.values())
    assert all(a["height"] >= a["width"] for a in assets.values())  # vertical


def test_resources_regenerates_only_filtered_scene(make_ctx):
    ctx = make_ctx()
    run_until(ctx, "creative_direction", "script", "scene_prep", "resource_generation")
    before = ctx.workspace.load("resources", "assets")
    ctx.scene_filter = {2}
    ResourcesAgent().run("resource_generation", ctx)
    after = ctx.workspace.load("resources", "assets")
    assert after["2"]["path"] != before["2"]["path"]
    assert all(after[k]["path"] == before[k]["path"] for k in before if k != "2")


# ---------------------------------------------------------------- 5. Voz
def test_voice_timeline_and_subtitles(make_ctx):
    ctx = make_ctx()
    run_until(ctx, "creative_direction", "script", "voice")
    vm = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
    assert 45 <= vm.total_duration_s <= 75
    for s in vm.scenes:
        if s.path:
            assert s.scene_duration_s >= s.voice_duration_s + s.voice_offset_s
    assert vm.cues and all(c.end_s > c.start_s for c in vm.cues)
    assert all(len(c.text) <= 40 for c in vm.cues)


def test_voice_requests_correction_on_overrun(make_ctx, mock_providers):
    mock_providers[next(k for k in mock_providers if k.value == "tts")].words_per_second = 0.8  # voz muy lenta
    ctx = make_ctx()
    run_until(ctx, "creative_direction", "script")
    r = VoiceAgent().run("voice", ctx)
    assert r.status == "in_review"
    assert r.corrections and all(c.target_agent == "scriptwriter" for c in r.corrections)


def test_voice_normalization():
    assert normalize_for_tts("Un 50% más 🐙 & mejor", "es") == "Un 50 por ciento más y mejor"


# ---------------------------------------------------------------- 6. Editor
def test_editor_incremental_render(make_ctx, mock_providers):
    ctx = make_ctx()
    run_until(ctx, *PIPE[:6])
    render = next(p for k, p in mock_providers.items() if k.value == "rendering")
    first = [op for op, _ in render.ops if op == "render_scene"]
    edit = ctx.workspace.load("scenes", "edit_manifest", EditManifest)
    n = len(edit.segments)
    assert len(first) == n
    # Rehacer solo la escena 1
    ctx.scene_filter = {1}
    ResourcesAgent().run("resource_generation", ctx)
    ctx.scene_filter = None
    r = EditorAgent().run("edit", ctx)
    assert r.metrics == {"rendered": 1, "reused": n - 1}


def test_editor_render_outputs_master_and_preview(make_ctx):
    ctx = make_ctx()
    run_until(ctx, *PIPE)
    assert (ctx.workspace.dir("exports") / "master_clean.mp4").exists()
    assert (ctx.workspace.dir("review") / "master_preview.mp4").exists()


# ---------------------------------------------------------------- 7. Sonido
def test_sound_mix_has_voice_music_and_sfx(make_ctx):
    ctx = make_ctx()
    run_until(ctx, *PIPE[:7])
    mix = json.loads((ctx.workspace.dir("sound") / "mix.wav").read_text())  # mock render escribe JSON
    vm = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
    voiced = sum(1 for s in vm.scenes if s.path)
    assert mix["tracks"] >= voiced + 1 + 1  # voces + música + al menos un efecto
    sm = ctx.workspace.load("sound", "sound_manifest")
    assert sm["music_asset_id"] and sm["sfx"]


# ---------------------------------------------------------------- 8. Revisor
def test_reviewer_scores_and_passes(make_ctx):
    ctx = make_ctx()
    r = run_until(ctx, *PIPE, "review")
    rep = ctx.workspace.load("review", "latest")
    assert 0 <= rep["score"] <= 100 and rep["passed"] and r.status == "completed"
    assert "viralidad" in rep["disclaimer"]


def test_reviewer_requests_targeted_corrections(make_ctx):
    llm = ScriptedLLM({"reviewer": lambda r: {
        "scores": {"hook": 2, "pacing": 3, "coherence": 3, "spelling": 5, "legibility": 5},
        "issues": [{"target_agent": "scriptwriter", "scene_index": 0, "reason": "Gancho flojo", "severity": "major"}],
        "summary": "Flojo"}}, fallback=LocalDraftLLM())
    ctx = make_ctx(llm=llm, settings={"review_threshold": 90})
    r = run_until(ctx, *PIPE, "review")
    assert r.status == "in_review"
    assert any(c.target_agent == "scriptwriter" and c.scene_index == 0 for c in r.corrections)


# ---------------------------------------------------------------- 9. Publicador
def test_publisher_exports_and_metadata_limits(make_ctx):
    ctx = make_ctx()
    run_until(ctx, *PIPE, "exports", "publish_prep")
    exports = ctx.workspace.load("exports", "exports")
    assert set(exports) == {"youtube_shorts", "instagram_reels", "tiktok"}
    pkg = ctx.workspace.load("exports", "publish_package")
    from ytauto.core.platforms import load_profiles
    profiles = load_profiles()
    for platform, item in pkg.items():  # la miniatura solo existe donde el perfil la admite
        assert bool(item["thumbnail"]) == profiles[platform].thumbnail.get("supported", False), platform
        assert item["issues"] == [] and Path(item["manual_dir"], "video.mp4").exists()


def test_publisher_never_publishes_without_authorization(make_ctx, mock_providers):
    ctx = make_ctx()
    run_until(ctx, *PIPE, "exports", "publish_prep")
    r = PublisherAgent().run("publish", ctx)
    pub = next(p for k, p in mock_providers.items() if k.value == "publishing")
    assert pub.published == []
    assert all(v["status"] == "skipped" for v in r.metrics["results"].values())


def test_publisher_publishes_only_authorized_platform(make_ctx, mock_providers):
    ctx = make_ctx(settings={"publish_authorizations": {"tiktok": "apr_1"}})
    run_until(ctx, *PIPE, "exports", "publish_prep")
    r = PublisherAgent().run("publish", ctx)
    pub = next(p for k, p in mock_providers.items() if k.value == "publishing")
    assert [p.platform for p in pub.published] == ["tiktok"]
    assert r.metrics["results"]["youtube_shorts"]["status"] == "skipped"
