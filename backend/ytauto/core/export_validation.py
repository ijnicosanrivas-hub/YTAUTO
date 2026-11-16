"""Validación de una exportación contra el perfil de su plataforma."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..providers.interfaces import MediaProbe
from .platforms import PlatformProfile

ASPECT_TOLERANCE = 0.01
BITRATE_ESTIMATE_MARGIN = 1.05


class ExportIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ExportValidation(BaseModel):
    platform: str
    ok: bool
    issues: list[ExportIssue] = Field(default_factory=list)
    checked: list[str] = Field(default_factory=list)  # comprobaciones realizadas (también las superadas)

    @property
    def errors(self) -> list[ExportIssue]:
        return [i for i in self.issues if i.severity == "error"]


def validate_export(probe: MediaProbe, profile: PlatformProfile) -> ExportValidation:
    f, enc = profile.file, profile.encode
    issues: list[ExportIssue] = []
    checked: list[str] = []

    def check(name: str, ok: bool, code: str, message: str, severity: Literal["error", "warning"] = "error") -> None:
        checked.append(name)
        if not ok:
            issues.append(ExportIssue(code=code, message=message, severity=severity))

    # ---- duración
    lo = max(profile.min_duration_s, f.platform_min_duration_s or 0)
    hi = min(profile.max_duration_s, f.platform_max_duration_s or profile.max_duration_s)
    check("duración", lo <= probe.duration_s <= hi, "duration",
          f"Duración {probe.duration_s:.2f}s fuera del rango {lo:g}-{hi:g}s")

    # ---- formato vertical y resolución
    w, h = probe.width or 0, probe.height or 0
    check("vertical 9:16", h > 0 and abs(w / h - 9 / 16) <= ASPECT_TOLERANCE, "aspect",
          f"Relación de aspecto {w}x{h}: se esperaba 9:16")
    check("resolución", (w, h) == (enc.width, enc.height), "resolution",
          f"Resolución {w}x{h}; el perfil pide {enc.width}x{enc.height}")
    if f.min_side is not None:
        check("lado mínimo", min(w, h) >= f.min_side, "min_side", f"Lado menor {min(w, h)} < {f.min_side}px")
    if f.max_side is not None:
        check("lado máximo", max(w, h) <= f.max_side or w <= f.max_side, "max_side",
              f"Dimensiones {w}x{h} superan el máximo de {f.max_side}px")

    # ---- códecs, contenedor y formato de píxel
    check("contenedor", (probe.container or "") in f.containers, "container",
          f"Contenedor {probe.container}; admitidos: {', '.join(f.containers)}")
    check("códec de vídeo", (probe.video_codec or "") in f.video_codecs, "video_codec",
          f"Códec de vídeo {probe.video_codec}; admitidos: {', '.join(f.video_codecs)}")
    check("códec de audio", (probe.audio_codec or "") in f.audio_codecs, "audio_codec",
          f"Códec de audio {probe.audio_codec}; admitidos: {', '.join(f.audio_codecs)}")
    if probe.pix_fmt is not None:
        check("formato de píxel", probe.pix_fmt in f.pix_fmts, "pix_fmt",
              f"Formato de píxel {probe.pix_fmt}; admitidos: {', '.join(f.pix_fmts)}")
    if probe.field_order is not None:
        check("progresivo", probe.field_order in ("progressive", "unknown"), "interlaced",
              f"Vídeo entrelazado ({probe.field_order}); debe ser progresivo")

    # ---- fps
    fps = probe.fps or 0.0
    if f.fps_min is not None and f.fps_max is not None:
        check("fps", f.fps_min <= fps <= f.fps_max, "fps", f"{fps:g} FPS fuera de {f.fps_min:g}-{f.fps_max:g}")
    check("fps del perfil", abs(fps - enc.fps) < 0.5, "fps_profile", f"{fps:g} FPS; el perfil pide {enc.fps}",
          severity="warning")

    # ---- audio
    check("audio presente", probe.has_audio, "no_audio", "El vídeo no tiene pista de audio")
    if f.max_audio_sample_rate is not None and probe.audio_sample_rate:
        check("frecuencia de audio", probe.audio_sample_rate <= f.max_audio_sample_rate, "audio_rate",
              f"Audio a {probe.audio_sample_rate} Hz; máximo {f.max_audio_sample_rate}")
    if probe.audio_channels is not None:
        check("canales de audio", probe.audio_channels in f.audio_channels, "audio_channels",
              f"{probe.audio_channels} canales; admitidos: {f.audio_channels}")

    # ---- tamaño y tasa de bits
    if f.max_size_mb is not None:
        mb = probe.size_bytes / 1_000_000
        check("tamaño", mb <= f.max_size_mb, "size", f"Fichero de {mb:.1f} MB; máximo {f.max_size_mb:g} MB")
    if f.max_video_bitrate_mbps is not None:
        rate = (probe.video_bit_rate_bps or probe.bit_rate_bps or 0) / 1e6
        check("tasa de bits", rate <= f.max_video_bitrate_mbps * BITRATE_ESTIMATE_MARGIN, "bitrate",
              f"Tasa de bits de vídeo {rate:.1f} Mbps; máximo {f.max_video_bitrate_mbps:g}")

    # ---- estructura MP4
    if f.require_moov_first and probe.moov_first is not None:
        check("moov al principio", probe.moov_first, "moov_not_first",
              "El átomo moov no está al principio del fichero (falta +faststart)")
    if f.forbid_edit_lists and probe.has_edit_list is not None:
        check("sin listas de edición", not probe.has_edit_list, "edit_list",
              "El MP4 contiene listas de edición (edts/elst), que la plataforma no admite")

    return ExportValidation(platform=profile.id, ok=not any(i.severity == "error" for i in issues),
                            issues=issues, checked=checked)
