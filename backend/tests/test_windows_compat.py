"""Compatibilidad con Windows, reproducida en cualquier sistema.

No sustituye a una prueba en un Windows real (no hay ninguno en el entorno de desarrollo), pero cubre lo que suele
romperse: rutas con espacios, «:» (letra de unidad), comillas y tildes; fuentes ausentes; BOM en .env;
consola cp1252 y codificación de los subprocesos.
"""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import ytauto.providers.rendering.ffmpeg as ffmod
from ytauto.core.settings import force_utf8_console, load_dotenv
from ytauto.providers.audio_synth import synth_music, write_wav
from ytauto.providers.interfaces import (
    AssembleSpec, FinalizeSpec, SceneRenderSpec, SubtitleCue, SubtitleStyle, TTSRequest, WordTiming,
)
from ytauto.providers.rendering.ffmpeg import BUNDLED_FONT, FFmpegRenderingProvider, concat_line
from ytauto.providers.voice.espeak import EspeakTTSProvider, find_binary

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg no instalado")
HOSTILE = "María O'Brien: vídeos & pruebas"  # espacios, «:», comilla, tilde y «&» en la ruta


def _image(path: Path, color=(40, 40, 40)) -> Path:
    Image.new("RGB", (1080, 1920), color).save(path)
    return path


def _bright_pixels(video: Path, ff: FFmpegRenderingProvider, at_s: float, tmp: Path) -> int:
    frame = ff.extract_frame(video, at_s, tmp / "f.png")
    with Image.open(frame) as im:
        px = im.convert("L").crop((0, 1100, 1080, 1700)).tobytes()  # zona de subtítulos
    return sum(1 for v in px if v > 200)


@needs_ffmpeg
def test_the_bundled_font_exists_and_has_its_license():
    assert BUNDLED_FONT.exists() and BUNDLED_FONT.stat().st_size > 100_000
    assert (BUNDLED_FONT.parent / "LICENSE-DejaVu.txt").exists()


@needs_ffmpeg
def test_full_pipeline_works_with_hostile_paths(tmp_path):
    """Escena con texto, ensamblado (cortes y fundidos) y render final con subtítulos, todo dentro de una ruta con
    espacios, «:», comillas y tildes: el equivalente de C:\\Users\\María O'Brien\\… en Windows."""
    work = tmp_path / HOSTILE
    work.mkdir()
    ff = FFmpegRenderingProvider()
    segs = []
    for i in range(3):
        out = work / f"escena {i}: ñ.mp4"
        ff.render_scene(SceneRenderSpec(scene_index=i, visual_path=_image(work / f"imagen {i}.png"), visual_kind="image",
                                        duration_s=1.5, shot_changes=2, on_screen_text="¿Qué pingüino? ñandú",
                                        out_path=out))
        segs.append(out)
    for transitions in (["cut", "cut"], ["fade", "cut"]):  # concat y xfade
        m = ff.assemble(AssembleSpec(segments=segs, transitions=transitions, transition_s=0.3,
                                     out_path=work / f"máster {transitions[0]}.mp4"))
        assert m.duration_s > 3.5
    audio = write_wav(work / "audio: pista.wav", synth_music("calm", 4.5))
    words = [WordTiming(word=w, start_s=0.5 + i * 0.4, end_s=0.9 + i * 0.4) for i, w in enumerate(["Hola", "pingüino", "ñandú"])]
    cue = SubtitleCue(start_s=0.5, end_s=1.7, text="Hola pingüino ñandú", words=words)
    out = ff.finalize(FinalizeSpec(video_path=work / "máster cut.mp4", audio_path=audio, subtitles=[cue],
                                   subtitle_style=SubtitleStyle(karaoke=False, mode="line", margin_v=420),
                                   draft=True, out_path=work / "final: ✔.mp4"))
    assert Path(out.path).exists()
    assert _bright_pixels(Path(out.path), ff, 1.0, work) > 500  # el subtítulo SE VE (texto blanco sobre gris oscuro)
    assert _bright_pixels(Path(out.path), ff, 4.2, work) < 50  # y desaparece cuando termina el subtítulo


@needs_ffmpeg
def test_subtitles_and_titles_render_without_the_system_font_inter(tmp_path, monkeypatch):
    """En Windows no existe Inter: se usa la fuente incluida (DejaVu Sans) y el texto sigue viéndose."""
    monkeypatch.setattr(ffmod, "DRAWTEXT_FONTS", [])  # simula un sistema sin Inter
    ff = FFmpegRenderingProvider()
    assert ff._font() == str(BUNDLED_FONT)
    assert ff._font_family(ff._font(), "Inter") == "DejaVu Sans"
    seg = ff.render_scene(SceneRenderSpec(scene_index=0, visual_path=_image(tmp_path / "a.png"), visual_kind="image",
                                          duration_s=2.0, on_screen_text="TÍTULO", out_path=tmp_path / "s.mp4"))
    audio = write_wav(tmp_path / "a.wav", synth_music("calm", 2.5))
    cue = SubtitleCue(start_s=0.2, end_s=1.8, text="Texto visible")
    out = ff.finalize(FinalizeSpec(video_path=Path(seg.path), audio_path=audio, subtitles=[cue],
                                   subtitle_style=SubtitleStyle(karaoke=False, mode="line"), draft=True,
                                   out_path=tmp_path / "f.mp4"))
    assert _bright_pixels(Path(out.path), ff, 1.0, tmp_path) > 300


def test_font_family_is_only_overridden_for_the_bundled_font():
    ff = FFmpegRenderingProvider()
    assert ff._font_family("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "Inter") == "Inter"
    assert ff._font_family(str(BUNDLED_FONT), "Inter") == "DejaVu Sans"


def test_concat_list_uses_forward_slashes_and_escapes_quotes(tmp_path):
    line = concat_line(tmp_path / "it's here" / "v.mp4")
    assert line.startswith("file '") and line.endswith("'\n")
    assert "\\" not in line.replace("'\\''", "")  # solo la secuencia de escape de la comilla lleva barra invertida
    assert "it'\\''s here" in line


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng no instalado")
def test_espeak_reads_accented_text_from_a_utf8_file_and_leaves_no_temp_files(tmp_path):
    work = tmp_path / HOSTILE
    work.mkdir()
    tts = EspeakTTSProvider()
    a = tts.synthesize(TTSRequest(text="¿Qué pingüino come ñandú? Ñoño.", language="es", out_path=work / "voz: ñ.wav"))
    assert a.duration_s > 1.0 and Path(a.path).exists()
    assert not list(work.glob("*.txt")) and not list(work.glob("*.raw.wav"))
    assert find_binary("espeak-ng")


def test_dotenv_with_bom_from_windows_notepad_is_read_correctly(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_bytes(b"\xef\xbb\xbfYTAUTO_API_TOKEN=abc123\r\nYTAUTO_LLM_PROVIDER=claude_cli\r\n")  # BOM + saltos CRLF
    monkeypatch.delenv("YTAUTO_API_TOKEN", raising=False)
    monkeypatch.delenv("YTAUTO_LLM_PROVIDER", raising=False)
    load_dotenv(env)
    import os
    assert os.environ["YTAUTO_API_TOKEN"] == "abc123"  # sin el BOM pegado al nombre de la variable
    assert os.environ["YTAUTO_LLM_PROVIDER"] == "claude_cli"


def test_console_in_cp1252_can_print_spanish_and_arrows():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    with pytest.raises(UnicodeEncodeError):
        stream.write("fase → completada ≈ 1 €")  # lo que pasaría en una consola de Windows
        stream.flush()
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    import sys
    old = sys.stdout
    sys.stdout = stream
    try:
        force_utf8_console()
        print("fase → completada ≈ 1 € ¿Qué?")
        sys.stdout.flush()
        assert sys.stdout.encoding.lower() == "utf-8"
    finally:
        sys.stdout = old
    force_utf8_console()  # un flujo sin reconfigure() no debe fallar


def test_claude_runner_uses_the_full_path_and_utf8(monkeypatch, tmp_path):
    from ytauto.llm import claude_cli
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(claude_cli.shutil, "which", lambda name: r"C:\Users\Ana\.local\bin\claude.exe")
    monkeypatch.setattr(claude_cli.subprocess, "run", fake_run)
    claude_cli._default_runner(["claude", "-p", "--model", "sonnet"], "¿Qué pingüino? ñandú", 30, tmp_path)
    assert seen["cmd"][0] == r"C:\Users\Ana\.local\bin\claude.exe" and seen["cmd"][1:] == ["-p", "--model", "sonnet"]
    assert seen["kw"]["encoding"] == "utf-8" and seen["kw"]["input"] == "¿Qué pingüino? ñandú"
