"""Pruebas de compatibilidad (contrato) para cualquier adaptador.

Se ejecutan en `pytest` sobre todos los adaptadores descubiertos y desde el panel
("Probar conexión"). Nunca se ejecutan sobre proveedores de pago sin permiso explícito,
y nunca publican nada (para publicación solo se comprueban requisitos).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image
from pydantic import BaseModel, Field

from ..core.models import AssetKind, MediaAsset
from .interfaces import (
    AssembleSpec, AudioMixSpec, AudioTrack, BaseProvider, FinalizeSpec, ImageRequest, MusicRequest,
    ProviderCategory, PublishRequest, SceneRenderSpec, SFXRequest, SubtitleRequest, TTSRequest, VideoRequest,
)


class ContractCheck(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class ContractReport(BaseModel):
    provider: str
    category: str
    passed: bool
    checks: list[ContractCheck] = Field(default_factory=list)
    skipped: str | None = None


class _Checker:
    def __init__(self):
        self.checks: list[ContractCheck] = []

    def ok(self, name: str, cond: bool, detail: str = "") -> bool:
        self.checks.append(ContractCheck(name=name, passed=bool(cond), detail=detail))
        return bool(cond)

    def asset(self, a, kind: AssetKind) -> None:
        self.ok("devuelve MediaAsset", isinstance(a, MediaAsset), type(a).__name__)
        if not isinstance(a, MediaAsset):
            return
        self.ok("tipo de recurso", a.kind is kind, a.kind.value)
        self.ok("fichero existe", Path(a.path).exists() and Path(a.path).stat().st_size > 0, a.path)
        self.ok("proveedor identificado", bool(a.provider), a.provider)
        self.ok("licencia registrada", a.license.name != "unknown", a.license.name)


def _tone(path: Path, seconds: float) -> Path:
    from .mock import write_tone
    return write_tone(path, seconds, rate=16000)


def _image(c: _Checker, p, d: Path) -> None:
    a = p.generate(ImageRequest(prompt="a lighthouse at night, vertical composition", search_query="lighthouse",
                                out_dir=d))
    c.asset(a, AssetKind.IMAGE)
    c.ok("dimensiones informadas", bool(a.width and a.height), f"{a.width}x{a.height}")
    c.ok("apto para 9:16", bool(a.width and a.height and min(a.width, a.height) >= 540), f"{a.width}x{a.height}")


def _video(c: _Checker, p, d: Path) -> None:
    a = p.generate(VideoRequest(prompt="ocean waves, vertical", search_query="ocean waves", duration_s=3, out_dir=d))
    c.asset(a, AssetKind.VIDEO)
    c.ok("duración informada", (a.duration_s or 0) > 0, str(a.duration_s))


def _tts(c: _Checker, p, d: Path) -> None:
    voices = p.list_voices("es")
    c.ok("lista voces", isinstance(voices, list) and len(voices) > 0, str(len(voices) if voices else 0))
    voice = voices[0].id if voices else None
    a = p.synthesize(TTSRequest(text="Hola, esto es una prueba de voz.", language="es", voice_id=voice,
                                out_path=d / "tts.wav"))
    c.asset(a, AssetKind.AUDIO_VOICE)
    c.ok("duración > 0", (a.duration_s or 0) > 0.3, str(a.duration_s))


def _music(c: _Checker, p, d: Path) -> None:
    a = p.get_track(MusicRequest(mood="calm", duration_s=8, out_dir=d))
    c.asset(a, AssetKind.AUDIO_MUSIC)
    c.ok("duración > 0", (a.duration_s or 0) > 0, str(a.duration_s))


def _sfx(c: _Checker, p, d: Path) -> None:
    for effect in ("whoosh", "impact"):
        a = p.get_effect(SFXRequest(effect=effect, out_dir=d))
        c.asset(a, AssetKind.AUDIO_SFX)


def _subtitle(c: _Checker, p, d: Path) -> None:
    audio = _tone(d / "voice.wav", 3.0)
    text = "Esto es una frase de prueba para alinear subtítulos correctamente."
    cues = p.align(SubtitleRequest(text=text, audio_path=audio, audio_duration_s=3.0, offset_s=10.0))
    c.ok("devuelve subtítulos", len(cues) > 0, str(len(cues)))
    if cues:
        c.ok("ordenados y sin solapes", all(b.start_s >= a.end_s - 0.01 for a, b in zip(cues, cues[1:])))
        c.ok("dentro de la locución", cues[0].start_s >= 9.95 and cues[-1].end_s <= 13.1,
             f"{cues[0].start_s}-{cues[-1].end_s}")
        words = " ".join(x.text for x in cues).split()
        c.ok("cubre todo el texto", words == text.split())


def _rendering(c: _Checker, p, d: Path) -> None:
    img = d / "frame.png"
    Image.new("RGB", (1080, 1920), (40, 80, 160)).save(img)
    segs = []
    for i in range(2):
        out = d / f"s{i}.mp4"
        a = p.render_scene(SceneRenderSpec(scene_index=i, visual_path=img, visual_kind="image", duration_s=2.0,
                                           camera_motion="slow_zoom_in", out_path=out))
        c.ok(f"render_scene {i}", Path(a.path).exists(), a.path)
        segs.append(out)
    master = p.assemble(AssembleSpec(segments=segs, transitions=["fade"], transition_s=0.3, out_path=d / "m.mp4"))
    c.ok("assemble", Path(master.path).exists())
    voice = _tone(d / "v.wav", 3.0)
    mix = p.mix_audio(AudioMixSpec(tracks=[AudioTrack(path=voice, start_s=0.2, role="voice")], duration_s=3.7,
                                   out_path=d / "mix.wav"))
    c.ok("mix_audio", Path(mix.path).exists())
    final = p.finalize(FinalizeSpec(video_path=master.path, audio_path=mix.path, out_path=d / "final.mp4"))
    c.ok("finalize", Path(final.path).exists())
    probe = p.probe(Path(final.path))
    c.ok("probe duración", abs(probe.duration_s - 3.7) < 0.35, f"{probe.duration_s:.2f}s (esperado 3.7)")
    c.ok("probe resolución", (probe.width, probe.height) == (1080, 1920), f"{probe.width}x{probe.height}")
    frame = p.extract_frame(Path(final.path), 1.0, d / "thumb.png")
    c.ok("extract_frame", Path(frame).exists())


def _storage(c: _Checker, p, d: Path) -> None:
    src = d / "x.txt"
    src.write_text("contrato")
    uri = p.put(src, "contract/x.txt")
    c.ok("put devuelve URI", bool(uri), uri)
    c.ok("exists", p.exists("contract/x.txt"))
    got = p.get("contract/x.txt", d / "y.txt")
    c.ok("get", Path(got).read_text(encoding="utf-8") == "contrato")
    p.delete("contract/x.txt")
    c.ok("delete", not p.exists("contract/x.txt"))


def _publishing(c: _Checker, p, d: Path) -> None:
    video = d / "v.mp4"
    video.write_bytes(b"\x00")
    platform = (p.platforms or ["youtube_shorts"])[0]
    issues = p.check_requirements(PublishRequest(platform=platform, video_path=video, title="t", description="d",
                                                 authorization_id=""))
    c.ok("check_requirements devuelve lista", isinstance(issues, list))
    c.ok("exige autorización", len(issues) > 0, "; ".join(issues))
    c.ok("declara plataformas", bool(p.platforms), ", ".join(p.platforms))


_RUNNERS: dict[ProviderCategory, Callable] = {
    ProviderCategory.IMAGE: _image, ProviderCategory.VIDEO: _video, ProviderCategory.TTS: _tts,
    ProviderCategory.MUSIC: _music, ProviderCategory.SFX: _sfx, ProviderCategory.SUBTITLE: _subtitle,
    ProviderCategory.RENDERING: _rendering, ProviderCategory.STORAGE: _storage,
    ProviderCategory.PUBLISHING: _publishing,
}


def run_contract(provider: BaseProvider, workdir: Path | None = None, allow_paid: bool = False) -> ContractReport:
    cat = provider.category
    if provider.is_paid and not allow_paid:
        return ContractReport(provider=provider.name, category=cat.value, passed=True,
                              skipped="Proveedor de pago: prueba de contrato omitida para no generar costes")
    c = _Checker()
    health = provider.health_check()
    c.ok("health_check", health.ok, health.message)
    if health.ok:
        with tempfile.TemporaryDirectory(dir=workdir) as tmp:
            try:
                _RUNNERS[cat](c, provider, Path(tmp))
            except Exception as e:  # noqa: BLE001
                c.ok("sin excepciones", False, f"{type(e).__name__}: {e}")
    return ContractReport(provider=provider.name, category=cat.value, passed=all(x.passed for x in c.checks),
                          checks=c.checks)
