"""Fase 8: perfiles verificados, textos por plataforma, validación de exportaciones y paquetes manuales."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from ytauto.core.captions import (
    clean_hashtag, compose, fit_hashtags, utf16_len, validate_fields, youtube_tags_length,
)
from ytauto.core.errors import PhaseBlocked
from ytauto.core.export_validation import validate_export
from ytauto.core.mp4 import inspect_mp4
from ytauto.core.platforms import load_profiles
from ytauto.providers.interfaces import FinalizeSpec, MediaProbe, SceneRenderSpec
from ytauto.providers.rendering.ffmpeg import FFmpegRenderingProvider

PROFILES = load_profiles()
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg no instalado")


# ---------------------------------------------------------------- perfiles frente a la documentación oficial
def test_every_profile_is_verified_with_sources_and_declares_unverified_fields():
    assert set(PROFILES) == {"youtube_shorts", "instagram_reels", "tiktok"}
    for p in PROFILES.values():
        assert p.is_verified and p.verified_at == "2026-11-16" and len(p.sources) >= 2
        assert all(s.startswith("https://") for s in p.sources)
        assert "safe_area" in p.unverified  # las plataformas no publican márgenes orgánicos: no se finge
        assert p.encode.width == 1080 and p.encode.height == 1920 and p.encode.container == "mp4"
        assert 45 <= p.min_duration_s < p.max_duration_s <= 75  # producto: 45–75 s


def test_instagram_profile_matches_documented_requirements():
    f, m, e = PROFILES["instagram_reels"].file, PROFILES["instagram_reels"].metadata, PROFILES["instagram_reels"].encode
    assert (f.fps_min, f.fps_max) == (23, 60) and f.max_size_mb == 300 and f.max_video_bitrate_mbps == 25
    assert f.max_audio_sample_rate == 48000 and f.require_moov_first and f.forbid_edit_lists
    assert set(f.video_codecs) == {"h264", "hevc"} and f.platform_min_duration_s == 3 and f.platform_max_duration_s == 900
    assert (m.caption_max, m.hashtags_max, m.mentions_max) == (2200, 30, 20)
    assert e.edit_lists is False  # la codificación evita las listas de edición
    assert PROFILES["instagram_reels"].publish.public_url_required


def test_tiktok_profile_matches_documented_requirements_and_limits_of_unaudited_clients():
    p = PROFILES["tiktok"]
    assert (p.file.fps_min, p.file.fps_max, p.file.min_side, p.file.max_side) == (23, 60, 360, 4096)
    assert p.file.max_size_mb == 4096 and p.metadata.caption_unit == "utf16" and p.metadata.caption_max == 2200
    assert p.publish.unaudited_private_only and p.publish.user_must_choose_privacy


def test_youtube_profile_matches_documented_limits():
    p = PROFILES["youtube_shorts"]
    assert p.metadata.title_max_chars == 100 and p.metadata.description_max_bytes == 5000
    assert p.metadata.tags_total_chars == 500 and p.file.platform_max_duration_s == 180


# ---------------------------------------------------------------- medición de textos
def test_utf16_and_bytes_are_measured_like_the_platforms():
    assert utf16_len("a😀") == 3  # el emoji ocupa 2 unidades UTF-16
    assert len("ñ".encode()) == 2


def test_youtube_tag_length_follows_documented_example():
    assert youtube_tags_length(["Foo-Baz"]) == 7  # ejemplo de la documentación
    assert youtube_tags_length(["Foo Baz"]) == 9  # con espacios cuenta las comillas
    assert youtube_tags_length(["a", "b"]) == 3  # la coma separadora cuenta


def test_compose_per_platform_mode():
    yt = compose(PROFILES["youtube_shorts"], "Título", "Descripción", ["pulpos", "#mar"])
    assert yt.title == "Título" and yt.description.endswith("#pulpos #mar") and yt.tags == ["pulpos", "mar"]
    ig = compose(PROFILES["instagram_reels"], "Título", "Pie", ["#a"])
    assert ig.caption == "Pie\n\n#a"
    tk = compose(PROFILES["tiktok"], "ignorado", "Pie", ["#a"])
    assert tk.title == tk.caption == "Pie\n\n#a"  # en TikTok el campo title ES el pie
    assert clean_hashtag("¡hola mundo!") == "#holamundo"


def test_youtube_description_is_limited_in_bytes_not_characters():
    p = PROFILES["youtube_shorts"]
    ok_chars = "ñ" * 2400  # 2400 caracteres = 4800 bytes
    assert validate_fields(p, compose(p, "t", ok_chars, [])) == []
    too_many_bytes = "ñ" * 2600  # 2600 caracteres pero 5200 bytes
    assert any("bytes" in i for i in validate_fields(p, compose(p, "t", too_many_bytes, [])))
    assert any("100" in i for i in validate_fields(p, compose(p, "x" * 101, "d", [])))
    assert any("<" in i for i in validate_fields(p, compose(p, "a<b", "d", [])))


def test_tiktok_caption_counts_utf16_units():
    p = PROFILES["tiktok"]
    assert validate_fields(p, compose(p, "t", "a" * 2190, [])) == []
    assert any("UTF-16" in i for i in validate_fields(p, compose(p, "t", "😀" * 1101, [])))  # 2202 unidades


def test_instagram_hashtag_and_caption_limits():
    p = PROFILES["instagram_reels"]
    tags = [f"#t{i}" for i in range(31)]
    assert any("31 hashtags" in i for i in validate_fields(p, compose(p, "t", "d", tags)))
    assert any("2200" in i for i in validate_fields(p, compose(p, "t", "x" * 2300, [])))
    assert any("menciones" in i for i in validate_fields(p, compose(p, "t", " ".join(f"@u{i}" for i in range(21)), [])))


def test_fit_hashtags_trims_instead_of_rejecting():
    p = PROFILES["instagram_reels"]
    fields = fit_hashtags(p, "t", "d" * 2150, [f"#etiqueta{i}" for i in range(20)])
    assert validate_fields(p, fields) == [] and 0 < len(fields.hashtags) < 20


# ---------------------------------------------------------------- estructura MP4 y validación con ficheros reales
@pytest.fixture(scope="module")
def real_files(tmp_path_factory):
    """Tres MP4 reales: estándar, sin listas de edición (Instagram) y sin faststart."""
    d = tmp_path_factory.mktemp("exp")
    ff = FFmpegRenderingProvider()
    img = d / "f.png"
    Image.new("RGB", (1080, 1920), (30, 90, 160)).save(img)
    seg = ff.render_scene(SceneRenderSpec(scene_index=0, visual_path=img, visual_kind="image", duration_s=4.0,
                                          out_path=d / "s.mp4"))
    from ytauto.providers.audio_synth import synth_music, write_wav
    audio = write_wav(d / "a.wav", synth_music("calm", 4.2))
    out = {}
    for name, prof in (("tiktok", PROFILES["tiktok"]), ("instagram", PROFILES["instagram_reels"])):
        out[name] = Path(ff.finalize(FinalizeSpec(video_path=Path(seg.path), audio_path=audio,
                                                  profile=prof.encode, draft=True, out_path=d / f"{name}.mp4")).path)
    nofast = d / "nofast.mp4"  # remux sin faststart
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out["tiktok"]), "-c", "copy", str(nofast)], check=True)
    out["nofaststart"] = nofast
    out["ff"] = ff
    return out


def short(prof):
    """El perfil real, con un rango de duración corto para poder probar con clips de segundos."""
    return prof.model_copy(update={"min_duration_s": 1, "max_duration_s": 10})


@needs_ffmpeg
def test_mp4_structure_inspector(real_files):
    std, ig, nf = (inspect_mp4(real_files[k]) for k in ("tiktok", "instagram", "nofaststart"))
    assert std.moov_first and std.has_edit_list  # la codificación estándar lleva listas de edición
    assert ig.moov_first and not ig.has_edit_list  # la de Instagram, no
    assert not nf.moov_first


@needs_ffmpeg
def test_instagram_export_passes_real_validation_and_av_stays_aligned(real_files):
    ff = real_files["ff"]
    probe = ff.probe(real_files["instagram"])
    v = validate_export(probe, short(PROFILES["instagram_reels"]))
    assert v.ok, [i.message for i in v.issues]
    assert {"moov al principio", "sin listas de edición", "tasa de bits"} <= set(v.checked)
    # Sin listas de edición, vídeo y audio siguen alineados (CTS negativos)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time", "-of", "csv=p=0",
                          str(real_files["instagram"])], capture_output=True, text=True).stdout
    starts = {line.split(",")[0]: float(line.split(",")[1]) for line in out.split() if "," in line}
    assert abs(starts["video"] - starts["audio"]) < 0.05


@needs_ffmpeg
def test_standard_export_is_rejected_by_instagram_but_valid_for_tiktok(real_files):
    probe = real_files["ff"].probe(real_files["tiktok"])
    assert validate_export(probe, short(PROFILES["tiktok"])).ok
    ig = validate_export(probe, short(PROFILES["instagram_reels"]))
    assert not ig.ok and any(i.code == "edit_list" for i in ig.errors)


@needs_ffmpeg
def test_missing_faststart_is_detected(real_files):
    probe = real_files["ff"].probe(real_files["nofaststart"])
    v = validate_export(probe, short(PROFILES["instagram_reels"]))
    assert any(i.code == "moov_not_first" for i in v.errors)


def _probe(**kw) -> MediaProbe:
    base = dict(path="x.mp4", duration_s=60, width=1080, height=1920, fps=30, video_codec="h264", audio_codec="aac",
                has_audio=True, size_bytes=60_000_000, pix_fmt="yuv420p", field_order="progressive",
                audio_sample_rate=48000, audio_channels=2, container="mp4", moov_first=True, has_edit_list=False,
                bit_rate_bps=8_200_000, video_bit_rate_bps=8_000_000)
    return MediaProbe(**{**base, **kw})


@pytest.mark.parametrize("platform,kw,code", [
    ("instagram_reels", {"fps": 15}, "fps"),
    ("tiktok", {"fps": 70}, "fps"),
    ("instagram_reels", {"size_bytes": 310_000_000}, "size"),
    ("instagram_reels", {"video_bit_rate_bps": 30_000_000}, "bitrate"),
    ("instagram_reels", {"audio_sample_rate": 96000}, "audio_rate"),
    ("instagram_reels", {"audio_channels": 6}, "audio_channels"),
    ("tiktok", {"width": 1920, "height": 1080}, "aspect"),
    ("tiktok", {"duration_s": 30}, "duration"),
    ("youtube_shorts", {"duration_s": 90}, "duration"),  # el producto limita a 75 s aunque Shorts admita 180
    ("tiktok", {"video_codec": "mpeg4"}, "video_codec"),
    ("tiktok", {"audio_codec": "mp3"}, "audio_codec"),
    ("tiktok", {"pix_fmt": "yuv444p"}, "pix_fmt"),
    ("tiktok", {"field_order": "tt"}, "interlaced"),
    ("tiktok", {"has_audio": False}, "no_audio"),
    ("youtube_shorts", {"container": "mkv"}, "container"),
])
def test_validator_detects_each_violation(platform, kw, code):
    v = validate_export(_probe(**kw), PROFILES[platform])
    assert not v.ok and code in {i.code for i in v.errors}, [i.code for i in v.issues]


@pytest.mark.parametrize("platform", ["youtube_shorts", "instagram_reels", "tiktok"])
def test_a_correct_export_passes_every_platform(platform):
    assert validate_export(_probe(), PROFILES[platform]).ok


# ---------------------------------------------------------------- agente: caché, bloqueo y paquetes manuales
PIPE = ["creative_direction", "script", "scene_prep", "resource_generation", "voice", "edit", "sound", "render"]


def _agents():
    from ytauto.agents.director import DirectorAgent
    from ytauto.agents.editor import EditorAgent
    from ytauto.agents.publisher import PublisherAgent
    from ytauto.agents.resources import ResourcesAgent
    from ytauto.agents.scriptwriter import ScriptwriterAgent
    from ytauto.agents.sound import SoundAgent
    from ytauto.agents.voice import VoiceAgent
    return {"creative_direction": DirectorAgent(), "script": ScriptwriterAgent(), "scene_prep": ResourcesAgent(),
            "resource_generation": ResourcesAgent(), "voice": VoiceAgent(), "edit": EditorAgent(),
            "sound": SoundAgent(), "render": EditorAgent(), "exports": PublisherAgent(),
            "publish_prep": PublisherAgent()}


def _run(ctx, *phases):
    agents = _agents()
    out = None
    for p in phases:
        out = agents[p].run(p, ctx)
    return out


def test_exports_are_cached_and_only_reencoded_when_inputs_change(make_ctx, mock_providers):
    ctx = make_ctx()
    _run(ctx, *PIPE)
    render = next(p for k, p in mock_providers.items() if k.value == "rendering")
    r1 = _run(ctx, "exports")
    assert r1.metrics == {"reused": 0, "encoded": 3}
    n_finalize = sum(1 for op, _ in render.ops if op == "finalize")
    r2 = _run(ctx, "exports")  # mismas entradas → nada se recodifica
    assert r2.metrics == {"reused": 3, "encoded": 0}
    assert sum(1 for op, _ in render.ops if op == "finalize") == n_finalize
    ctx.spec = ctx.spec.model_copy(update={"subtitle_mode": "word_pop"})  # cambia el estilo → se rehacen
    assert _run(ctx, "exports").metrics["encoded"] == 3


def test_invalid_export_blocks_the_phase_with_the_reason(make_ctx, mock_providers):
    ctx = make_ctx()
    _run(ctx, *PIPE)
    render = next(p for k, p in mock_providers.items() if k.value == "rendering")
    original = render.probe
    render.probe = lambda path, analyze=False: original(path, analyze).model_copy(update={"fps": 15.0})
    with pytest.raises(PhaseBlocked) as e:
        _run(ctx, "exports")
    assert e.value.code == "export_validation" and "FPS" in e.value.reason


def test_manual_packages_explain_platform_limitations(make_ctx):
    ctx = make_ctx()
    _run(ctx, *PIPE, "exports", "publish_prep")
    manual = ctx.workspace.dir("exports") / "manual"
    tiktok = (manual / "tiktok" / "LEEME.txt").read_text(encoding="utf-8")
    assert "privado" in tiktok and "5 usuarios" in tiktok and "verificado" in tiktok
    ig = (manual / "instagram_reels" / "LEEME.txt").read_text(encoding="utf-8")
    assert "URL pública" in ig
    assert (manual / "youtube_shorts" / "miniatura.jpg").exists() and not (manual / "tiktok" / "miniatura.jpg").exists()
    assert (manual / "tiktok" / "video.mp4").exists() and (manual / "tiktok" / "publicacion.json").exists()
    pkg = ctx.workspace.load("exports", "publish_package")
    assert pkg["tiktok"]["unaudited_private_only"] and pkg["instagram_reels"]["public_url_required"]
    assert all(v["issues"] == [] for v in pkg.values())


def test_publish_without_integration_keeps_manual_package(make_ctx, mock_providers):
    from ytauto.providers.gateway import DirectGateway
    from ytauto.providers.interfaces import ProviderCategory
    providers = {k: v for k, v in mock_providers.items() if k is not ProviderCategory.PUBLISHING}
    ctx = make_ctx(providers=DirectGateway(providers), settings={"publish_authorizations": {"tiktok": "apr_1"}})
    _run(ctx, *PIPE, "exports", "publish_prep")
    from ytauto.agents.publisher import PublisherAgent
    r = PublisherAgent().run("publish", ctx)
    res = r.metrics["results"]["tiktok"]
    assert res["status"] == "manual_package" and Path(res["package_path"]).exists()
    assert r.metrics["results"]["youtube_shorts"]["package_path"]  # también sin autorización: material preparado


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="requiere espeak-ng")
def test_real_production_exports_are_valid_for_all_three_platforms(tmp_path):
    """Producción real (FFmpeg + espeak-ng): cada MP4 cumple los requisitos de SU plataforma."""
    from ytauto.app import build_app
    from ytauto.core.models import Platform, ProjectSpec, ProjectStatus
    from ytauto.core.settings import Settings
    st = Settings.from_env(load_env_file=False)
    st.data_dir, st.projects_dir = tmp_path / "data", tmp_path / "projects"
    st.db_path, st.logs_dir, st.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    st.llm_provider = "local_draft"
    app = build_app(st)
    spec = ProjectSpec(name="3p", topic="los arrecifes de coral", duration_s=45, require_script_approval=False,
                       platforms=[Platform.YOUTUBE_SHORTS, Platform.INSTAGRAM_REELS, Platform.TIKTOK])
    pid = app.orchestrator.create_project(spec)
    for gate in ("final_approval", "publish_decision"):
        app.worker.schedule(pid)
        app.worker.run_until_idle()
        app.orchestrator.approve(pid, gate)
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    assert app.store.get_project(pid).status is ProjectStatus.COMPLETED
    ff = FFmpegRenderingProvider()
    root = st.projects_dir / pid
    sizes = {}
    for platform, prof in PROFILES.items():
        mp4 = root / "exports" / f"{platform}.mp4"
        probe = ff.probe(mp4)
        v = validate_export(probe, prof)
        assert v.ok, (platform, [i.message for i in v.issues])
        assert probe.moov_first and (platform != "instagram_reels" or probe.has_edit_list is False)
        assert (root / "exports" / "manual" / platform / "video.mp4").exists()
        sizes[platform] = probe.size_bytes
    # El máster limpio es único: las tres versiones salen del mismo máster y la misma mezcla
    assert (root / "exports" / "master_clean.mp4").exists()
    exports = app.store.get_phase(pid, "exports").result["metrics"]
    assert exports == {"reused": 0, "encoded": 3}
