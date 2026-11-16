"""Proveedores simulados: cumplen los contratos sin coste ni dependencias pesadas.

Generan ficheros mínimos reales (PNG, WAV) para que los agentes puedan trabajar, y un
renderizador simulado que registra las operaciones. Se usan en pruebas y como referencia
de cómo escribir un adaptador.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import wave
from pathlib import Path

from PIL import Image

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ..interfaces import (
    AssembleSpec, AudioMixSpec, CostEstimate, FinalizeSpec, ImageGenerationProvider, ImageRequest,
    MediaProbe, MusicGenerationProvider, MusicRequest, PublishingProvider, PublishRequest, PublishResult,
    SceneRenderSpec, SFXRequest, SoundEffectsProvider, StorageProvider, TextToSpeechProvider, TTSRequest,
    VideoGenerationProvider, VideoRenderingProvider, VideoRequest, Voice,
)

MOCK_LICENSE = License(name="generated", attribution="mock provider", commercial_use=True)


def write_tone(path: Path, duration_s: float, freq: float = 220.0, rate: int = 8000, amp: float = 0.2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(duration_s * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)))
                               for i in range(n)))
    return path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


class MockImageProvider(ImageGenerationProvider):
    name = "mock_image"
    display_name = "Imágenes simuladas"

    def capabilities(self):
        return {"max_width": 1080, "max_height": 1920, "aspect_ratios": ["9:16"]}

    def generate(self, request: ImageRequest) -> MediaAsset:
        h = hashlib.sha256(f"{request.prompt}|{request.seed}|{len(request.exclude_hashes)}".encode()).hexdigest()
        color = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        path = request.out_dir / f"img_{h[:10]}.png"
        Image.new("RGB", (request.width, request.height), color).save(path)
        return MediaAsset(kind=AssetKind.IMAGE, path=str(path), width=request.width, height=request.height,
                          provider=self.name, prompt=request.prompt, perceptual_hash=h[:16], sha256=h,
                          license=MOCK_LICENSE)


class MockPaidImageProvider(MockImageProvider):
    """Simula un proveedor de pago (para probar presupuesto y autorización)."""
    name = "mock_paid_image"
    display_name = "Imágenes de pago (simulado)"
    is_paid = True
    is_local = False
    required_credentials = ["api_key"]

    def estimate_cost(self, operation, request):
        return CostEstimate(amount_eur=0.04, units=1, unit_name="image")

    def generate(self, request: ImageRequest) -> MediaAsset:
        asset = super().generate(request)
        asset.provider, asset.cost_eur = self.name, 0.04
        return asset


class FailingImageProvider(MockImageProvider):
    name = "failing_image"

    def generate(self, request: ImageRequest) -> MediaAsset:
        raise ProviderError(self.name, "servicio caído (simulado)")


class MockVideoProvider(VideoGenerationProvider):
    name = "mock_video"

    def generate(self, request: VideoRequest) -> MediaAsset:
        path = request.out_dir / f"clip_{abs(hash(request.prompt)) % 10**8}.mp4"
        path.write_bytes(b"\x00")
        return MediaAsset(kind=AssetKind.VIDEO, path=str(path), width=1080, height=1920,
                          duration_s=request.duration_s, provider=self.name, license=MOCK_LICENSE)


class MockTTSProvider(TextToSpeechProvider):
    name = "mock_tts"
    display_name = "Voz simulada"
    words_per_second = 2.5

    def list_voices(self, language=None):
        return [Voice(id="mock-es-1", name="Mock Español", language="es", gender="female"),
                Voice(id="mock-en-1", name="Mock English", language="en", gender="male")]

    def synthesize(self, request: TTSRequest) -> MediaAsset:
        words = len(request.text.split())
        dur = max(0.4, words / (self.words_per_second * request.speed))
        write_tone(request.out_path, dur, freq=180)
        return MediaAsset(kind=AssetKind.AUDIO_VOICE, path=str(request.out_path), duration_s=round(dur, 3),
                          provider=self.name, prompt=request.text, license=MOCK_LICENSE)


class MockMusicProvider(MusicGenerationProvider):
    name = "mock_music"

    def get_track(self, request: MusicRequest) -> MediaAsset:
        path = write_tone(request.out_dir / "music_mock.wav", min(request.duration_s, 10), freq=110)
        return MediaAsset(kind=AssetKind.AUDIO_MUSIC, path=str(path), duration_s=min(request.duration_s, 10),
                          provider=self.name, license=MOCK_LICENSE)


class MockSFXProvider(SoundEffectsProvider):
    name = "mock_sfx"

    def get_effect(self, request: SFXRequest) -> MediaAsset:
        path = write_tone(request.out_dir / f"sfx_{request.effect.replace(':', '_')}.wav", 0.4, freq=880)
        return MediaAsset(kind=AssetKind.AUDIO_SFX, path=str(path), duration_s=0.4, provider=self.name,
                          license=MOCK_LICENSE)


class MockRenderingProvider(VideoRenderingProvider):
    """Renderizador simulado: escribe ficheros JSON con la operación y conoce sus duraciones."""
    name = "mock_render"

    def __init__(self, params=None, credentials=None):
        super().__init__(params, credentials)
        self.ops: list[tuple[str, str]] = []

    def _write(self, path: Path, op: str, duration: float, **extra) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"op": op, "duration_s": duration, **extra}, default=str), encoding="utf-8")
        self.ops.append((op, str(path)))

    def render_scene(self, spec: SceneRenderSpec) -> MediaAsset:
        self._write(spec.out_path, "render_scene", spec.duration_s, scene=spec.scene_index)
        return MediaAsset(kind=AssetKind.VIDEO_SEGMENT, path=str(spec.out_path), duration_s=spec.duration_s,
                          width=spec.width, height=spec.height, provider=self.name, scene_index=spec.scene_index)

    def assemble(self, spec: AssembleSpec) -> MediaAsset:
        durs = [json.loads(Path(p).read_text(encoding="utf-8"))["duration_s"] for p in spec.segments]
        overlap = sum(spec.transition_s for t in spec.transitions if t != "cut")
        total = round(sum(durs) - overlap, 3)
        self._write(spec.out_path, "assemble", total)
        return MediaAsset(kind=AssetKind.VIDEO_MASTER, path=str(spec.out_path), duration_s=total, provider=self.name)

    def mix_audio(self, spec: AudioMixSpec) -> MediaAsset:
        self._write(spec.out_path, "mix_audio", spec.duration_s, tracks=len(spec.tracks))
        return MediaAsset(kind=AssetKind.AUDIO_MIX, path=str(spec.out_path), duration_s=spec.duration_s,
                          provider=self.name)

    def finalize(self, spec: FinalizeSpec) -> MediaAsset:
        d = json.loads(Path(spec.video_path).read_text(encoding="utf-8"))["duration_s"]
        self._write(spec.out_path, "finalize", d, width=spec.profile.width, height=spec.profile.height,
                    fps=spec.profile.fps, subs=len(spec.subtitles))
        return MediaAsset(kind=AssetKind.VIDEO_EXPORT, path=str(spec.out_path), duration_s=d, provider=self.name)

    def probe(self, path: Path, analyze: bool = False) -> MediaProbe:
        info = json.loads(Path(path).read_text(encoding="utf-8"))
        return MediaProbe(path=str(path), duration_s=info["duration_s"], width=info.get("width", 1080),
                          height=info.get("height", 1920), fps=info.get("fps", 30), video_codec="h264",
                          audio_codec="aac", has_audio=True, size_bytes=Path(path).stat().st_size,
                          pix_fmt="yuv420p", field_order="progressive", audio_sample_rate=48000, audio_channels=2,
                          container="mp4", moov_first=True, has_edit_list=False, bit_rate_bps=8_200_000,
                          video_bit_rate_bps=8_000_000,
                          integrated_lufs=-14.0 if analyze else None, true_peak_db=-1.2 if analyze else None)

    def extract_frame(self, video: Path, at_s: float, out_path: Path) -> Path:
        Image.new("RGB", (1080, 1920), (30, 30, 60)).save(out_path)
        return out_path


class MockStorageProvider(StorageProvider):
    name = "mock_storage"

    def __init__(self, params=None, credentials=None):
        super().__init__(params, credentials)
        self.items: dict[str, bytes] = {}

    def put(self, local_path, key):
        self.items[key] = Path(local_path).read_bytes()
        return f"mock://{key}"

    def get(self, key, dest):
        Path(dest).write_bytes(self.items[key])
        return Path(dest)

    def exists(self, key):
        return key in self.items

    def delete(self, key):
        self.items.pop(key, None)


class MockPublishingProvider(PublishingProvider):
    name = "mock_publisher"
    platforms = ["youtube_shorts", "instagram_reels", "tiktok"]
    supports_direct_publish = True

    def __init__(self, params=None, credentials=None):
        super().__init__(params, credentials)
        self.published: list[PublishRequest] = []

    def check_requirements(self, request):
        return [] if request.authorization_id else ["Falta autorización"]

    def publish(self, request: PublishRequest) -> PublishResult:
        if self.check_requirements(request):
            raise ProviderError(self.name, "Publicación sin autorización", transient=False)
        self.published.append(request)
        return PublishResult(platform=request.platform, status="uploaded_private",
                             url=f"https://example.invalid/{request.platform}/1", external_id="1")
