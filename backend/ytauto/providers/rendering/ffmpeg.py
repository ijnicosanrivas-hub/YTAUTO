"""Motor de renderizado local basado en FFmpeg (principal por defecto).

- Escenas: imagen con movimiento de cámara (zoompan) y sub-planos (punch-in) para evitar
  estatismo, o clip de vídeo recortado a 9:16; texto en pantalla opcional.
- Ensamblado: `xfade` para transiciones y `concat` para cortes secos.
- Mezcla: voz + música con ducking (`sidechaincompress`) + efectos; normalización en dos
  pasadas con `loudnorm` (−14 LUFS integrados, −1 dBTP).
- Final: subtítulos ASS (karaoke) con márgenes de plataforma, H.264/AAC, `+faststart`.
- Análisis: ffprobe + ebur128 + blackdetect + freezedetect + silencedetect.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..interfaces import (
    AssembleSpec, AudioMixSpec, FinalizeSpec, HealthStatus, MediaProbe, SceneRenderSpec, SubtitleStyle,
    VideoRenderingProvider,
)
from .ass import write_ass

FONT_DIRS = ["/usr/share/fonts", "/Library/Fonts", "C:/Windows/Fonts"]
DRAWTEXT_FONTS = ["/usr/share/fonts/opentype/inter/Inter-Black.otf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
                  "C:/Windows/Fonts/arialbd.ttf"]
XFADE_OK = {"fade", "slideleft", "slideright", "slideup", "slidedown", "wipeleft", "wiperight", "zoomin",
            "circleopen", "circleclose", "dissolve", "smoothleft", "smoothright"}
INTERNAL = License(name="derived", attribution="ytauto render", commercial_use=True)


class FFmpegRenderingProvider(VideoRenderingProvider):
    """Renderizado, mezcla y análisis local con FFmpeg."""
    name = "ffmpeg"
    display_name = "FFmpeg (local)"
    default_priority = 0
    default_params = {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe", "preset": "veryfast", "final_preset": "faster",
                      "threads": 0, "timeout_s": 900}

    # ------------------------------------------------------------------ utilidades
    def _run(self, args: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
        cmd = [self.params["ffmpeg"], "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args]
        if self.params.get("threads"):
            cmd[1:1] = ["-threads", str(self.params["threads"])]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout or self.params["timeout_s"])
        except FileNotFoundError as e:
            raise ProviderError(self.name, "FFmpeg no está instalado", transient=False) from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError(self.name, "FFmpeg superó el tiempo máximo", transient=True) from e
        if proc.returncode != 0:
            raise ProviderError(self.name, f"FFmpeg falló: {proc.stderr.strip()[-1500:]}", transient=False)
        return proc

    def _duration(self, path: Path) -> float:
        proc = subprocess.run([self.params["ffprobe"], "-v", "error", "-show_entries", "format=duration",
                               "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
        try:
            return float(proc.stdout.strip())
        except ValueError as e:
            raise ProviderError(self.name, f"No se pudo leer la duración de {path}", transient=False) from e

    @staticmethod
    def _font() -> str | None:
        return next((f for f in DRAWTEXT_FONTS if Path(f).exists()), None)

    def capabilities(self):
        return {"max_resolution": "4K", "transitions": sorted(XFADE_OK), "subtitles": "ASS karaoke",
                "loudness": "EBU R128 two-pass", "motions": ["slow_zoom_in", "zoom_out", "pan_left", "pan_right",
                                                             "pan_up", "ken_burns", "static"]}

    def health_check(self) -> HealthStatus:
        if not shutil.which(self.params["ffmpeg"]) or not shutil.which(self.params["ffprobe"]):
            return HealthStatus(ok=False, message="ffmpeg/ffprobe no encontrados en PATH")
        out = subprocess.run([self.params["ffmpeg"], "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        missing = [f for f in ("zoompan", "xfade", "ass", "loudnorm", "sidechaincompress") if f" {f} " not in out]
        if missing:
            return HealthStatus(ok=False, message=f"FFmpeg sin filtros necesarios: {missing}")
        ver = subprocess.run([self.params["ffmpeg"], "-version"], capture_output=True, text=True).stdout.split("\n")[0]
        return HealthStatus(ok=True, message=ver)

    def _asset(self, kind: AssetKind, path: Path, **kw) -> MediaAsset:
        return MediaAsset(kind=kind, path=str(path), sha256=sha256_file(path), provider=self.name, license=INTERNAL, **kw)

    # ------------------------------------------------------------------ escenas
    @staticmethod
    def _motion(motion: str, frames: int, w: int, h: int, fps: int, variant: int) -> str:
        n = max(1, frames - 1)
        p = f"(on/{n})"
        center_x, center_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        # Variantes de encuadre para sub-planos (centro, arriba, abajo).
        anchor_y = [center_y, "(ih-ih/zoom)*0.25", "(ih-ih/zoom)*0.75"][variant % 3]
        exprs = {
            "slow_zoom_in": (f"1.0+0.16*{p}", center_x, anchor_y),
            "zoom_out": (f"1.16-0.16*{p}", center_x, anchor_y),
            "pan_left": ("1.18", f"(iw-iw/zoom)*(1-{p})", anchor_y),
            "pan_right": ("1.18", f"(iw-iw/zoom)*{p}", anchor_y),
            "pan_up": ("1.18", center_x, f"(ih-ih/zoom)*(1-{p})"),
            "ken_burns": (f"1.05+0.12*{p}", f"(iw-iw/zoom)*(0.2+0.6*{p})", f"(ih-ih/zoom)*(0.7-0.4*{p})"),
            "static": ("1.0", center_x, center_y),
        }
        z, x, y = exprs.get(motion, exprs["slow_zoom_in"])
        return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps}"

    def render_scene(self, spec: SceneRenderSpec) -> MediaAsset:
        spec.out_path.parent.mkdir(parents=True, exist_ok=True)
        w, h, fps = spec.width, spec.height, spec.fps
        shots = max(1, spec.shot_changes)
        motions = [spec.camera_motion]
        cycle = ["slow_zoom_in", "pan_right", "zoom_out", "pan_left", "pan_up", "ken_burns"]
        for i in range(1, shots):
            motions.append(cycle[(cycle.index(spec.camera_motion) + i) % len(cycle)
                                 if spec.camera_motion in cycle else i % len(cycle)])
        total_frames = max(1, round(spec.duration_s * fps))
        frames_per = [total_frames // shots + (1 if i < total_frames % shots else 0) for i in range(shots)]
        text_filter = ""
        tmpdir = Path(tempfile.mkdtemp(prefix="ytscene_", dir=spec.out_path.parent))
        try:
            if spec.on_screen_text and self._font():
                lines, size = fit_text(spec.on_screen_text, w)
                for n, line in enumerate(lines):  # una capa por línea → cada línea centrada
                    tf = tmpdir / f"text{n}.txt"
                    tf.write_text(line, encoding="utf-8")
                    y = int(h * 0.14 + n * size * 1.18)
                    text_filter += (f",drawtext=fontfile='{self._font()}':textfile='{tf}':fontsize={size}:"
                                    f"fontcolor=white:borderw={max(3, size // 14)}:bordercolor=black@0.85:"
                                    f"x=(w-text_w)/2:y={y}:alpha='min(1,t/0.25)'")
            parts = []
            for i, (motion, nf) in enumerate(zip(motions, frames_per)):
                out = tmpdir / f"shot{i}.mp4"
                dur = nf / fps
                # Base 1.25x para tener margen de movimiento sin bordes.
                bw, bh = int(w * 1.25) // 2 * 2, int(h * 1.25) // 2 * 2
                cover = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase:flags=lanczos,"
                         f"crop={bw}:{bh},setsar=1")
                if spec.visual_kind == "image":
                    vf = f"{cover},{self._motion(motion, nf, w, h, fps, i)},format=yuv420p"
                    inp = ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(spec.visual_path)]
                else:
                    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p"
                    inp = ["-stream_loop", "-1", "-ss", f"{i * dur:.3f}", "-i", str(spec.visual_path), "-t", f"{dur:.3f}"]
                vf += text_filter if i == 0 else ""
                self._run([*inp, "-vf", vf, "-frames:v", str(nf), "-an", "-c:v", "libx264", "-preset",
                           self.params["preset"], "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)])
                parts.append(out)
            if len(parts) == 1:
                shutil.move(str(parts[0]), spec.out_path)
            else:
                lst = tmpdir / "list.txt"
                lst.write_text("".join(f"file '{p}'\n" for p in parts))
                self._run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(spec.out_path)])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return self._asset(AssetKind.VIDEO_SEGMENT, spec.out_path, duration_s=round(total_frames / fps, 3),
                           width=w, height=h, scene_index=spec.scene_index)

    # ------------------------------------------------------------------ ensamblado
    def assemble(self, spec: AssembleSpec) -> MediaAsset:
        if len(spec.transitions) != len(spec.segments) - 1:
            raise ProviderError(self.name, "transitions debe tener len(segments)-1 elementos", transient=False)
        spec.out_path.parent.mkdir(parents=True, exist_ok=True)
        durs = [self._duration(p) for p in spec.segments]
        if all(t == "cut" for t in spec.transitions):
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=spec.out_path.parent) as f:
                f.write("".join(f"file '{Path(p).resolve()}'\n" for p in spec.segments))
            try:
                self._run(["-f", "concat", "-safe", "0", "-i", f.name, "-c", "copy", str(spec.out_path)])
            finally:
                Path(f.name).unlink(missing_ok=True)
        else:
            inputs: list[str] = []
            for p in spec.segments:
                inputs += ["-i", str(p)]
            chains = [f"[{i}:v]settb=AVTB,fps={spec.fps},format=yuv420p[v{i}]" for i in range(len(spec.segments))]
            acc, acc_dur = "v0", durs[0]
            for i, t in enumerate(spec.transitions, start=1):
                out = f"x{i}"
                if t == "cut":
                    # concat cambia la base de tiempos: se normaliza para el siguiente xfade.
                    chains.append(f"[{acc}][v{i}]concat=n=2:v=1:a=0,settb=AVTB,fps={spec.fps}[{out}]")
                    acc_dur += durs[i]
                else:
                    tr = min(spec.transition_s, durs[i] / 2, acc_dur / 2)
                    name = t if t in XFADE_OK else "fade"
                    chains.append(f"[{acc}][v{i}]xfade=transition={name}:duration={tr:.3f}:"
                                  f"offset={acc_dur - tr:.3f}[{out}]")
                    acc_dur += durs[i] - tr
                acc = out
            self._run([*inputs, "-filter_complex", ";".join(chains), "-map", f"[{acc}]", "-an", "-c:v", "libx264",
                       "-preset", self.params["preset"], "-crf", "18", "-pix_fmt", "yuv420p", str(spec.out_path)])
        return self._asset(AssetKind.VIDEO_MASTER, spec.out_path, duration_s=round(self._duration(spec.out_path), 3))

    # ------------------------------------------------------------------ audio
    def mix_audio(self, spec: AudioMixSpec) -> MediaAsset:
        spec.out_path.parent.mkdir(parents=True, exist_ok=True)
        if not spec.tracks:
            self._run(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{spec.duration_s:.3f}",
                       str(spec.out_path)])
            return self._asset(AssetKind.AUDIO_MIX, spec.out_path, duration_s=spec.duration_s)
        inputs: list[str] = []
        chains: list[str] = []
        buses: dict[str, list[str]] = {"voice": [], "music": [], "sfx": []}
        for i, t in enumerate(spec.tracks):
            if t.loop:
                inputs += ["-stream_loop", "-1"]
            inputs += ["-i", str(t.path)]
            delay = int(round(t.start_s * 1000))
            f = [f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo"]
            if t.loop:
                f.append(f"atrim=0:{max(0.1, spec.duration_s - t.start_s):.3f}")
            if t.fade_in_s:
                f.append(f"afade=t=in:d={t.fade_in_s}")
            if t.fade_out_s:
                f.append(f"afade=t=out:st={max(0.0, spec.duration_s - t.start_s - t.fade_out_s):.3f}:d={t.fade_out_s}")
            f.append(f"volume={t.gain_db}dB")
            if delay:
                f.append(f"adelay={delay}|{delay}")
            chains.append(",".join(f) + f"[t{i}]")
            buses[t.role].append(f"[t{i}]")

        def bus(name: str) -> str | None:
            items = buses[name]
            if not items:
                return None
            if len(items) == 1:
                chains.append(f"{items[0]}anull[{name}]")
            else:
                chains.append(f"{''.join(items)}amix=inputs={len(items)}:normalize=0:dropout_transition=0[{name}]")
            return f"[{name}]"

        voice, music, sfx = bus("voice"), bus("music"), bus("sfx")
        final_inputs = []
        if voice and music and spec.duck_music_under_voice:
            # La voz se rellena hasta la duración total: si no, el compresor (y con él la música)
            # terminaría con la última frase y el vídeo acabaría en silencio.
            chains.append(f"{voice}apad=whole_dur={spec.duration_s:.3f},asplit=2[vmain][vsc]")
            chains.append(f"{music}[vsc]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350:"
                          f"makeup=1[ducked]")
            final_inputs += ["[vmain]", "[ducked]"]
        else:
            final_inputs += [x for x in (voice, music) if x]
        if sfx:
            final_inputs.append(sfx)
        dur = f"{spec.duration_s:.3f}"
        if len(final_inputs) == 1:
            chains.append(f"{final_inputs[0]}apad,atrim=0:{dur}[pre]")
        else:
            chains.append(f"{''.join(final_inputs)}amix=inputs={len(final_inputs)}:normalize=0:dropout_transition=0,"
                          f"apad,atrim=0:{dur}[pre]")
        with tempfile.TemporaryDirectory(dir=spec.out_path.parent) as tmp:
            pre = Path(tmp) / "premix.wav"
            self._run([*inputs, "-filter_complex", ";".join(chains), "-map", "[pre]", "-ar", "48000",
                       "-c:a", "pcm_s16le", str(pre)])
            # Normalización en dos pasadas (medición + corrección lineal).
            measure = subprocess.run([self.params["ffmpeg"], "-hide_banner", "-nostdin", "-i", str(pre), "-af",
                                      f"loudnorm=I={spec.target_lufs}:TP={spec.true_peak_db}:LRA=11:print_format=json",
                                      "-f", "null", "-"], capture_output=True, text=True)
            m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure.stderr, re.DOTALL)
            if m:
                st = json.loads(m.group(0))
                ln = (f"loudnorm=I={spec.target_lufs}:TP={spec.true_peak_db}:LRA=11:measured_I={st['input_i']}:"
                      f"measured_TP={st['input_tp']}:measured_LRA={st['input_lra']}:measured_thresh="
                      f"{st['input_thresh']}:offset={st['target_offset']}:linear=true")
            else:
                ln = f"loudnorm=I={spec.target_lufs}:TP={spec.true_peak_db}:LRA=11"
            # Limitador final de seguridad para no superar el pico verdadero.
            limit = 10 ** ((spec.true_peak_db - 0.3) / 20)
            self._run(["-i", str(pre), "-af", f"{ln},alimiter=limit={limit:.4f}:level=disabled,aresample=48000",
                       "-t", dur, "-ar", "48000", "-c:a", "pcm_s16le", str(spec.out_path)])
        return self._asset(AssetKind.AUDIO_MIX, spec.out_path, duration_s=spec.duration_s)

    # ------------------------------------------------------------------ final
    def finalize(self, spec: FinalizeSpec) -> MediaAsset:
        p = spec.profile
        spec.out_path.parent.mkdir(parents=True, exist_ok=True)
        audio_dur = self._duration(Path(spec.audio_path))
        video_dur = self._duration(Path(spec.video_path))
        vf = [f"scale={p.width}:{p.height}:force_original_aspect_ratio=increase:flags=lanczos",
              f"crop={p.width}:{p.height}", "setsar=1", f"fps={p.fps}"]
        if video_dur < audio_dur:
            vf.append(f"tpad=stop_mode=clone:stop_duration={audio_dur - video_dur + 0.1:.3f}")
        with tempfile.TemporaryDirectory(dir=spec.out_path.parent) as tmp:
            if spec.subtitles and spec.subtitle_style:
                ass = write_ass(spec.subtitles, spec.subtitle_style, Path(tmp) / "subs.ass", p.width, p.height)
                fontsdir = next((d for d in FONT_DIRS if Path(d).exists()), None)
                vf.append(f"ass='{ass}'" + (f":fontsdir='{fontsdir}'" if fontsdir else ""))
            vf.append(f"format={p.pix_fmt}")
            meta = []
            for k, v in spec.metadata.items():
                meta += ["-metadata", f"{k}={v}"]
            bufsize = f"{int(re.sub(r'[^0-9]', '', p.max_bitrate) or 10) * 2}M"
            self._run(["-i", str(spec.video_path), "-i", str(spec.audio_path), "-map", "0:v:0", "-map", "1:a:0",
                       "-vf", ",".join(vf), "-c:v", p.video_codec,
                       "-preset", self.params["preset"] if spec.draft else self.params["final_preset"],
                       "-profile:v", "high", "-b:v", p.video_bitrate, "-maxrate", p.max_bitrate, "-bufsize", bufsize,
                       "-r", str(p.fps), "-c:a", p.audio_codec, "-b:a", p.audio_bitrate, "-ar", str(p.audio_sample_rate),
                       "-ac", "2", "-t", f"{audio_dur:.3f}", "-movflags", "+faststart", *meta, str(spec.out_path)])
        return self._asset(AssetKind.VIDEO_EXPORT, spec.out_path, duration_s=round(self._duration(spec.out_path), 3),
                           width=p.width, height=p.height)

    # ------------------------------------------------------------------ análisis
    def probe(self, path: Path, analyze: bool = False) -> MediaProbe:
        proc = subprocess.run([self.params["ffprobe"], "-v", "error", "-print_format", "json", "-show_format",
                               "-show_streams", str(path)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise ProviderError(self.name, f"ffprobe falló: {proc.stderr[-500:]}", transient=False)
        info = json.loads(proc.stdout)
        v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        fps = None
        if v and v.get("avg_frame_rate", "0/0") != "0/0":
            n, d = v["avg_frame_rate"].split("/")
            fps = round(float(n) / float(d), 3) if float(d) else None
        probe = MediaProbe(
            path=str(path), duration_s=float(info["format"].get("duration", 0.0)),
            width=v.get("width") if v else None, height=v.get("height") if v else None, fps=fps,
            video_codec=v.get("codec_name") if v else None, audio_codec=a.get("codec_name") if a else None,
            has_audio=a is not None, size_bytes=int(info["format"].get("size", 0)),
        )
        if analyze:
            self._analyze(Path(path), probe, has_video=v is not None, has_audio=a is not None)
        return probe

    def _analyze(self, path: Path, probe: MediaProbe, has_video: bool, has_audio: bool) -> None:
        parts, maps = [], []
        if has_video:
            parts.append("[0:v]blackdetect=d=0.3:pix_th=0.10,freezedetect=n=0.001:d=2[vo]")
            maps += ["-map", "[vo]"]
        if has_audio:
            parts.append("[0:a]ebur128=peak=true,silencedetect=n=-45dB:d=1[ao]")
            maps += ["-map", "[ao]"]
        if not parts:
            return
        proc = subprocess.run([self.params["ffmpeg"], "-hide_banner", "-nostdin", "-i", str(path), "-filter_complex",
                               ";".join(parts), *maps, "-f", "null", "-"], capture_output=True, text=True,
                              timeout=self.params["timeout_s"])
        err = proc.stderr
        summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
        m = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
        probe.integrated_lufs = float(m.group(1)) if m else None
        m = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
        probe.true_peak_db = float(m.group(1)) if m and m.group(1) != "-inf" else None
        probe.black_segments = [(float(s), float(e)) for s, e in
                                re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
        fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", err)]
        fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", err)]
        probe.frozen_segments = list(zip(fs, fe + [probe.duration_s] * (len(fs) - len(fe))))
        ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
        se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
        probe.silence_segments = list(zip(ss, se + [probe.duration_s] * (len(ss) - len(se))))

    def extract_frame(self, video: Path, at_s: float, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(["-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1", str(out_path)])
        return out_path


def fit_text(text: str, width: int, max_lines: int = 3) -> tuple[list[str], int]:
    """Parte el texto en líneas y elige un tamaño que quepa en el 84 % del ancho."""
    import textwrap
    words = text.strip()
    for chars in (12, 14, 16, 18, 22, 26):
        lines = textwrap.wrap(words, width=chars)
        if len(lines) <= max_lines:
            break
    longest = max(len(x) for x in lines) or 1
    # Ancho medio de un carácter en fuentes bold ≈ 0,62 del tamaño.
    size = int(min(width * 0.10, width * 0.84 / (longest * 0.62)))
    return lines[:max_lines], max(36, size)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def frames(duration_s: float, fps: int) -> int:
    return max(1, math.ceil(duration_s * fps))
