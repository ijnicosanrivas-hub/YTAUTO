"""Fase 6: calidad de vídeo corto — retención, ajuste voz/escena, subtítulos y montaje incremental real."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ytauto.agents.scriptwriter import check_script
from ytauto.agents.voice import MAX_SCENE_GAP_S, VoiceAgent, fit_scene
from ytauto.core.models import CreativeBrief, Script, ScriptScene, Section
from ytauto.core.narrative import NarrativeTemplate
from ytauto.core.retention import retention_checks
from ytauto.core.timeline import EditManifest, EditSegment, VoiceManifest, VoiceScene
from ytauto.providers.interfaces import SubtitleCue, SubtitleRequest, SubtitleStyle, TTSRequest, WordTiming
from ytauto.providers.rendering.ass import build_ass

needs_tools = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("espeak-ng")),
                                 reason="requiere ffmpeg y espeak-ng")
TPL = NarrativeTemplate.load()


# ---------------------------------------------------------------- guion: ni corto ni largo
def _brief(durs):
    from ytauto.core.models import ScenePlan
    secs = [Section.HOOK] + [Section.DEVELOPMENT] * (len(durs) - 2) + [Section.CLOSING]
    return CreativeBrief(concept="c", tone="t", visual_style="v", pacing="p", target_duration_s=int(sum(durs)),
                         music_direction="m", scenes=[ScenePlan(index=i, section=s, duration_s=d, purpose="p",
                                                                visual_direction="v") for i, (s, d) in
                                                      enumerate(zip(secs, durs))])


def _script(texts, durs):
    return Script(internal_title="t", topic="t", narrative_goal="g", hook=texts[0], closing=texts[-1], music="m",
                  scenes=[ScriptScene(index=i, section=Section.DEVELOPMENT, duration_s=d, narration=t, visual_notes="v")
                          for i, (t, d) in enumerate(zip(texts, durs))])


def test_script_too_short_is_rejected():
    durs = [3, 10, 10, 10, 10, 7]
    script = _script(["Gancho potente aquí ya."] + ["Una frase corta."] * 4 + ["Fin del vídeo."], durs)
    issues = check_script(script, _brief(durs), TPL, "es", 50)
    assert any("demasiado corta" in i for i in issues)


# ---------------------------------------------------------------- voz ajustada a la escena
def test_fit_scene_removes_dead_air_but_never_cuts_voice():
    assert fit_scene(planned_s=8.0, voice_s=3.0) == pytest.approx(3.0 + 0.15 + 0.35 + MAX_SCENE_GAP_S)
    assert fit_scene(planned_s=3.0, voice_s=4.0) == pytest.approx(4.0 + 0.15 + 0.35)
    assert fit_scene(planned_s=5.0, voice_s=0.2) >= 1.5


def test_short_narration_requests_lengthening_then_falls_back():
    scenes = [VoiceScene(index=i, path="x", voice_duration_s=2.0, scene_duration_s=3.3, planned_duration_s=8.0)
              for i in range(6)]
    m = VoiceManifest(scenes=scenes)
    corr = []
    VoiceAgent._fit_total(m, 60, corr, can_request=True)
    assert corr and all(c.target_agent == "scriptwriter" for c in corr)
    m2 = VoiceManifest(scenes=[s.model_copy() for s in scenes])
    corr2 = []
    note = VoiceAgent._fit_total(m2, 60, corr2, can_request=False)
    assert not corr2 and note and m2.total_duration_s >= 51  # último recurso: alarga hasta el 85 %


# ---------------------------------------------------------------- retención medida con datos reales
def _manifests(hook=2.5, first_offset=0.15, gap=0.5, shot=3.0):
    vs = [VoiceScene(index=0, path="v0", voice_duration_s=hook - first_offset - 0.3, scene_duration_s=hook,
                     voice_offset_s=first_offset),
          VoiceScene(index=1, path="v1", voice_duration_s=5.0, scene_duration_s=5.0 + 0.15 + gap, start_s=hook)]
    em = EditManifest(segments=[EditSegment(index=0, path="a", duration_s=hook, input_hash="h", shots=1),
                                EditSegment(index=1, path="b", duration_s=shot * 2, input_hash="h", shots=2)],
                      transitions=["cut"], transition_s=0.3, video_path="m", duration_s=10)
    return VoiceManifest(scenes=vs), em


def test_retention_checks_pass_for_good_edit():
    v, e = _manifests()
    checks = retention_checks(v, e, TPL, "medium")
    assert all(c.passed for c in checks), [(c.name, c.detail) for c in checks]
    assert sum(c.max_points for c in checks) == 15


@pytest.mark.parametrize("kw,name", [({"hook": 5.0}, "gancho ≤ 3 s"), ({"first_offset": 1.2}, "voz desde el inicio"),
                                     ({"gap": 3.0}, "sin tiempos muertos"), ({"shot": 6.0}, "cambios visuales frecuentes")])
def test_retention_checks_detect_problems(kw, name):
    v, e = _manifests(**kw)
    failed = {c.name for c in retention_checks(v, e, TPL, "medium") if not c.passed}
    assert name in failed


def test_reviewer_score_sums_to_100():
    from ytauto.agents.reviewer import sync_checks, technical_checks
    from ytauto.providers.interfaces import MediaProbe
    v, e = _manifests()
    probe = MediaProbe(path="x", duration_s=60, width=1080, height=1920, fps=30, video_codec="h264", audio_codec="aac",
                       integrated_lufs=-14, true_peak_db=-1)
    total = sum(c.max_points for c in technical_checks(probe, v, 30) + sync_checks(v, 60)
                + retention_checks(v, e, TPL, "medium"))
    assert total == 60  # + 40 editoriales = 100


# ---------------------------------------------------------------- subtítulos
def test_subtitle_modes():
    cue = SubtitleCue(start_s=1, end_s=2, text="Hola mundo", words=[WordTiming(word="Hola", start_s=1, end_s=1.4),
                                                                    WordTiming(word="mundo", start_s=1.4, end_s=2)])
    karaoke = build_ass([cue], SubtitleStyle(mode="karaoke"))
    pop = build_ass([cue], SubtitleStyle(mode="word_pop"))
    line = build_ass([cue], SubtitleStyle(mode="line"))
    assert "\\kf40" in karaoke
    assert pop.count("Dialogue:") == 2 and "\\fscx112" in pop
    assert "\\kf" not in line and line.count("Dialogue:") == 1
    # En modo línea el color principal es el blanco base, no el de acento
    assert "&H00FFFFFF" in line.split("Style: Default,")[1].split(",")[2]


@needs_tools
def test_acoustic_alignment_follows_real_pauses(tmp_path):
    from ytauto.providers.subtitle.acoustic import AcousticSubtitleProvider, speech_segments
    from ytauto.providers.voice.espeak import EspeakTTSProvider
    text = "Los pulpos tienen tres corazones. Y su sangre es azul, como el cobre. ¿Lo sabías?"
    a = EspeakTTSProvider().synthesize(TTSRequest(text=text, out_path=tmp_path / "v.wav"))
    segs = speech_segments(a.path, a.duration_s)
    cues = AcousticSubtitleProvider().align(SubtitleRequest(text=text, audio_path=a.path,
                                                            audio_duration_s=a.duration_s, offset_s=10.0))
    words = [w for c in cues for w in c.words]
    assert " ".join(w.word for w in words) == text
    # Ninguna palabra empieza dentro de una pausa real (tolerancia 60 ms)
    for w in words:
        t = w.start_s - 10.0
        assert any(s - 0.06 <= t <= e + 0.06 for s, e in segs), (w.word, t, segs)
    # Cada frase arranca cerca del inicio de su tramo de voz
    starts = [w.start_s - 10.0 for w in words if w.word in ("Y", "¿Lo")]
    for st in starts:
        assert min(abs(st - s) for s, _ in segs) < 0.1


# ---------------------------------------------------------------- montaje incremental con FFmpeg real
@pytest.mark.slow
@needs_tools
def test_redo_single_scene_rerenders_only_that_scene_with_real_ffmpeg(tmp_path):
    from ytauto.app import build_app
    from ytauto.core.models import Platform, ProjectSpec
    from ytauto.core.settings import Settings
    st = Settings.from_env(load_env_file=False)
    st.data_dir, st.projects_dir = tmp_path / "data", tmp_path / "projects"
    st.db_path, st.logs_dir, st.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    st.llm_provider = "local_draft"
    app = build_app(st)
    pid = app.orchestrator.create_project(ProjectSpec(name="r", topic="los glaciares", duration_s=45,
                                                      require_script_approval=False, platforms=[Platform.TIKTOK],
                                                      subtitle_mode="word_pop"))
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    first = app.store.get_phase(pid, "edit").result["metrics"]
    scenes_dir = st.projects_dir / pid / "scenes"
    before = {p.name: p.stat().st_mtime for p in scenes_dir.glob("s*.mp4")}
    app.orchestrator.redo_scenes(pid, [2], reason="otra imagen")
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    after = app.store.get_phase(pid, "edit").result["metrics"]
    assert first["rendered"] > 1 and after == {"rendered": 1, "reused": first["rendered"] - 1}
    # Los segmentos son inmutables (nombre = hash de entradas): ninguno se reescribe y solo aparece uno nuevo.
    unchanged = [n for n, m in before.items() if (scenes_dir / n).exists() and (scenes_dir / n).stat().st_mtime == m]
    new_files = {p.name for p in scenes_dir.glob("s*.mp4")} - set(before)
    assert len(unchanged) == len(before) and len(new_files) == 1 and next(iter(new_files)).startswith("s02_")
    review = app.store.get_phase(pid, "review")
    assert review.status.value == "completed"
    assert Path(st.projects_dir / pid / "review" / "master_preview.mp4").exists()


def test_small_deficit_is_absorbed_without_spending_rounds_and_keeps_safety_margin():
    scenes = [VoiceScene(index=i, path="x", voice_duration_s=4.0, scene_duration_s=4.9, planned_duration_s=5.0)
              for i in range(9)]  # 44,1 s para un objetivo de 45 s
    m = VoiceManifest(scenes=scenes)
    corr = []
    VoiceAgent._fit_total(m, 45, corr, can_request=True)
    assert corr == [] and m.total_duration_s >= 45.3
