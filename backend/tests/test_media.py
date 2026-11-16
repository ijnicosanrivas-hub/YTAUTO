"""Motor audiovisual local: FFmpeg, voz, imágenes, música, efectos, biblioteca y E2E real."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from ytauto.core.errors import ProviderError
from ytauto.providers.audio_synth import pick_mood
from ytauto.providers.image.local import LocalLibraryImageProvider, ProceduralImageProvider
from ytauto.providers.interfaces import (
    AssembleSpec, AudioMixSpec, AudioTrack, FinalizeSpec, ImageRequest, MusicRequest, SceneRenderSpec, SFXRequest,
    SubtitleCue, SubtitleStyle, TTSRequest, WordTiming,
)
from ytauto.providers.music.local import ProceduralMusicProvider
from ytauto.providers.rendering.ass import build_ass
from ytauto.providers.rendering.ffmpeg import FFmpegRenderingProvider, fit_text
from ytauto.providers.sound.local import SynthSFXProvider
from ytauto.providers.voice.espeak import EspeakTTSProvider

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg no instalado")
needs_espeak = pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng no instalado")


@pytest.fixture(scope="module")
def ff():
    return FFmpegRenderingProvider()


def _img(path: Path, color) -> Path:
    Image.new("RGB", (1080, 1920), color).save(path)
    return path


@needs_ffmpeg
def test_assemble_mixing_cuts_and_transitions(ff, tmp_path):
    """Regresión: un corte seco seguido de un fundido rompía la base de tiempos de xfade."""
    segs = []
    for i, c in enumerate([(200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0)]):
        out = tmp_path / f"s{i}.mp4"
        ff.render_scene(SceneRenderSpec(scene_index=i, visual_path=_img(tmp_path / f"{i}.png", c),
                                        visual_kind="image", duration_s=1.5, out_path=out))
        segs.append(out)
    m = ff.assemble(AssembleSpec(segments=segs, transitions=["cut", "fade", "cut"], transition_s=0.3,
                                 out_path=tmp_path / "m.mp4"))
    assert abs(m.duration_s - (6.0 - 0.3)) < 0.1


@needs_ffmpeg
def test_scene_subshots_and_text(ff, tmp_path):
    a = ff.render_scene(SceneRenderSpec(scene_index=0, visual_path=_img(tmp_path / "a.png", (10, 80, 160)),
                                        visual_kind="image", duration_s=3.0, shot_changes=3,
                                        on_screen_text="UN TEXTO MUY LARGO QUE DEBE PARTIRSE EN VARIAS LÍNEAS",
                                        out_path=tmp_path / "s.mp4"))
    p = ff.probe(Path(a.path))
    assert (p.width, p.height) == (1080, 1920) and abs(p.duration_s - 3.0) < 0.05


def test_fit_text_wraps_and_fits():
    lines, size = fit_text("LOS SECRETOS MEJOR GUARDADOS DE LOS PULPOS DEL PACÍFICO", 1080)
    assert len(lines) <= 3
    assert max(len(x) for x in lines) * size * 0.62 <= 1080 * 0.85


@needs_ffmpeg
def test_mix_is_normalized_and_ducked(ff, tmp_path):
    music = ProceduralMusicProvider().get_track(MusicRequest(mood="epic", duration_s=8, out_dir=tmp_path))
    from ytauto.providers.audio_synth import synth_music, write_wav
    voice = write_wav(tmp_path / "v.wav", synth_music("calm", 3.0)[:, 0])
    whoosh = SynthSFXProvider().get_effect(SFXRequest(effect="whoosh", out_dir=tmp_path))
    mix = ff.mix_audio(AudioMixSpec(tracks=[
        AudioTrack(path=voice, start_s=1.0, role="voice"),
        AudioTrack(path=Path(music.path), role="music", gain_db=-14, loop=True, fade_in_s=0.5, fade_out_s=1),
        AudioTrack(path=Path(whoosh.path), start_s=4.0, role="sfx", gain_db=-9)],
        duration_s=8.0, out_path=tmp_path / "mix.wav"))
    p = ff.probe(Path(mix.path), analyze=True)
    assert abs(p.duration_s - 8.0) < 0.05
    # Regresión: la música no debe cortarse cuando termina la voz (antes acababa en silencio).
    assert not any(e - s >= 1.0 for s, e in p.silence_segments), p.silence_segments
    assert p.integrated_lufs is not None and -16.0 <= p.integrated_lufs <= -12.0
    assert p.true_peak_db is not None and p.true_peak_db <= -0.5


def test_ass_karaoke_generation():
    cue = SubtitleCue(start_s=1.0, end_s=2.0, text="Hola mundo",
                      words=[WordTiming(word="Hola", start_s=1.0, end_s=1.4), WordTiming(word="mundo", start_s=1.4, end_s=2.0)])
    ass = build_ass([cue], SubtitleStyle(margin_v=480, margin_h=140))
    assert "PlayResX: 1080" in ass and "{\\kf40}Hola" in ass and "{\\kf60}mundo" in ass
    assert ",140,140,480," in ass  # márgenes de zona segura de la plataforma


@needs_ffmpeg
def test_finalize_burns_subtitles_and_matches_audio_length(ff, tmp_path):
    seg = ff.render_scene(SceneRenderSpec(scene_index=0, visual_path=_img(tmp_path / "a.png", (40, 40, 40)),
                                          visual_kind="image", duration_s=2.0, out_path=tmp_path / "s.mp4"))
    from ytauto.providers.audio_synth import synth_music, write_wav
    audio = write_wav(tmp_path / "a.wav", synth_music("calm", 2.5))
    cue = SubtitleCue(start_s=0.2, end_s=1.8, text="Prueba de subtítulo")
    out = ff.finalize(FinalizeSpec(video_path=Path(seg.path), audio_path=audio, subtitles=[cue],
                                   subtitle_style=SubtitleStyle(), out_path=tmp_path / "f.mp4"))
    p = ff.probe(Path(out.path))
    assert p.video_codec == "h264" and p.audio_codec == "aac"
    assert abs(p.duration_s - 2.5) < 0.1  # el vídeo se alarga hasta el audio (sin cortes de voz)
    # El fotograma con subtítulo difiere del original (texto grabado)
    f1 = ff.extract_frame(Path(out.path), 1.0, tmp_path / "f1.png")
    with Image.open(f1) as im:
        assert im.getextrema()[0][1] > 200  # hay píxeles claros del texto sobre fondo gris oscuro


@needs_espeak
def test_espeak_voice_real_audio(tmp_path):
    tts = EspeakTTSProvider()
    voices = tts.list_voices("es")
    assert voices and all(not v.id.startswith("mb") for v in voices)
    a = tts.synthesize(TTSRequest(text="Los pulpos tienen tres corazones.", language="es", out_path=tmp_path / "v.wav"))
    b = tts.synthesize(TTSRequest(text="Los pulpos tienen tres corazones.", language="es", speed=1.3,
                                  out_path=tmp_path / "v2.wav"))
    assert 1.0 < a.duration_s < 4.0 and b.duration_s < a.duration_s


def test_procedural_image_is_vertical_and_varied(tmp_path):
    p = ProceduralImageProvider()
    a = p.generate(ImageRequest(prompt="pulpo en el mar", out_dir=tmp_path, seed=1))
    b = p.generate(ImageRequest(prompt="pulpo en el mar", out_dir=tmp_path, seed=2))
    assert (a.width, a.height) == (1080, 1920) and a.perceptual_hash != b.perceptual_hash
    with Image.open(a.path) as im:
        assert sum(im.convert("L").resize((1, 1)).getpixel((0, 0)) for _ in [0]) > 40  # no es casi negra


def test_music_mood_and_duration(tmp_path):
    assert pick_mood("música épica cinematográfica") == "epic"
    assert pick_mood("ambiente relajado") == "calm"
    m = ProceduralMusicProvider().get_track(MusicRequest(mood="intriga", duration_s=12, out_dir=tmp_path))
    import wave
    with wave.open(m.path) as w:
        assert w.getnframes() / w.getframerate() >= 12


def test_library_ignores_unlicensed_and_matches_tags(tmp_path):
    from helpers import build_library
    lib = build_library(tmp_path / "lib")
    p = LocalLibraryImageProvider(params={"root": str(lib)})
    a = p.generate(ImageRequest(prompt="", search_query="volcano eruption", out_dir=tmp_path))
    assert Path(a.path).name == "volcano_lava.jpg" and a.license.name == "CC0"
    with pytest.raises(ProviderError):
        p.generate(ImageRequest(prompt="", search_query="sin_licencia", out_dir=tmp_path))
    # Excluye imágenes ya usadas (hash perceptual)
    b = p.generate(ImageRequest(prompt="", search_query="volcano lava ocean", exclude_hashes=[a.perceptual_hash],
                                out_dir=tmp_path))
    assert Path(b.path).name != "volcano_lava.jpg"


# ---------------------------------------------------------------- producción real completa
@pytest.mark.slow
@needs_ffmpeg
@needs_espeak
def test_full_local_production_produces_valid_vertical_mp4(tmp_path):
    from ytauto.app import build_app
    from ytauto.core.models import Platform, ProjectSpec, ProjectStatus
    from ytauto.core.settings import Settings
    settings = Settings.from_env(load_env_file=False)
    settings.data_dir, settings.projects_dir = tmp_path / "data", tmp_path / "projects"
    settings.db_path, settings.logs_dir, settings.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    settings.llm_provider = "local_draft"
    app = build_app(settings)
    spec = ProjectSpec(name="E2E", topic="los volcanes submarinos", duration_s=45, require_script_approval=False,
                       platforms=[Platform.TIKTOK], intensity="high")
    pid = app.orchestrator.create_project(spec)
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    app.orchestrator.approve(pid, "final_approval")
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    app.orchestrator.approve(pid, "publish_decision")
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    assert app.store.get_project(pid).status is ProjectStatus.COMPLETED
    mp4 = settings.projects_dir / pid / "exports" / "tiktok.mp4"
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                      "-show_format", str(mp4)], capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    dur = float(info["format"]["duration"])
    assert 45 <= dur <= 75
    assert (v["width"], v["height"]) == (1080, 1920) and v["codec_name"] == "h264" and a["codec_name"] == "aac"
    assert abs(float(v["duration"]) - float(a["duration"])) < 0.15  # audio y vídeo sincronizados
    review = json.loads((settings.projects_dir / pid / "review" / "latest.json").read_text())
    failed = [c["name"] for c in review["technical"] if not c["passed"]]
    assert review["passed"] and failed == [], failed
    # Proveedores usados: todos locales y gratuitos
    assert app.provider_system.budget.ledger(pid) == []


@needs_ffmpeg
def test_delivered_aac_file_respects_the_true_peak_target(ff, tmp_path):
    """Regresión (hallada con Claude real): la mezcla cumplía −1 dBTP pero el MP4 final salía en −0,4 por el
    sobrepico del AAC. Señal con transitorios casi a fondo de escala sobre un fondo bajo: sin el margen reservado
    la mezcla queda en −1,3 y el MP4 final en −0,8 (incumple); con él, −2,3 y −2,0."""
    import numpy as np
    from ytauto.providers.audio_synth import SR, write_wav
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.02, 9 * SR)
    for t in (1.0, 3.0, 5.0, 7.0):
        i = int(t * SR)
        x[i:i + 40] += np.sin(np.linspace(0, 6 * np.pi, 40)) * 0.9
    voice = write_wav(tmp_path / "v.wav", x)
    mix = ff.mix_audio(AudioMixSpec(tracks=[AudioTrack(path=voice, role="voice")], duration_s=9.0,
                                    out_path=tmp_path / "mix.wav"))
    mix_peak = ff.probe(Path(mix.path), analyze=True).true_peak_db
    assert mix_peak is not None and mix_peak <= -1.8, mix_peak  # la mezcla reserva margen para el AAC
    img = tmp_path / "f.png"
    Image.new("RGB", (1080, 1920), (30, 30, 30)).save(img)
    seg = ff.render_scene(SceneRenderSpec(scene_index=0, visual_path=img, visual_kind="image", duration_s=9.0,
                                          out_path=tmp_path / "s.mp4"))
    final = ff.finalize(FinalizeSpec(video_path=Path(seg.path), audio_path=Path(mix.path), out_path=tmp_path / "f.mp4"))
    p = ff.probe(Path(final.path), analyze=True)
    assert p.true_peak_db is not None and p.true_peak_db <= -0.9, p.true_peak_db  # el MP4 ENTREGADO cumple −1 dBTP
