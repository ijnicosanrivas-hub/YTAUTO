"""Contratos estables de proveedores audiovisuales.

Los agentes dependen SOLO de estas interfaces y de los tipos de petición/respuesta aquí
definidos. Cualquier adaptador (local o comercial) debe cumplirlos y superar la batería
de pruebas de contrato en `tests/contract/`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from ...core.models import MediaAsset


class ProviderCategory(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    TTS = "tts"
    MUSIC = "music"
    SFX = "sfx"
    SUBTITLE = "subtitle"
    RENDERING = "rendering"
    STORAGE = "storage"
    PUBLISHING = "publishing"


class CostEstimate(BaseModel):
    amount_eur: float = 0.0
    units: float = 0.0
    unit_name: str = "operation"
    detail: str = ""


class HealthStatus(BaseModel):
    ok: bool
    message: str = ""
    latency_ms: float | None = None


class BaseProvider(ABC):
    """Base de todos los adaptadores."""

    category: ClassVar[ProviderCategory]
    name: ClassVar[str]
    display_name: ClassVar[str] = ""
    is_paid: ClassVar[bool] = False
    is_local: ClassVar[bool] = True
    # Orden por defecto al darse de alta automáticamente (menor = preferente).
    default_priority: ClassVar[int] = 100
    # Claves de credenciales requeridas (p. ej. ["api_key"]). Vacío = no requiere.
    required_credentials: ClassVar[list[str]] = []
    # Esquema simple de parámetros configurables: {nombre: valor_por_defecto}
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, params: dict[str, Any] | None = None, credentials: dict[str, str] | None = None):
        self.params = {**self.default_params, **(params or {})}
        self.credentials = credentials or {}

    def capabilities(self) -> dict[str, Any]:
        return {}

    def estimate_cost(self, operation: str, request: BaseModel) -> CostEstimate:
        return CostEstimate()

    def health_check(self) -> HealthStatus:
        missing = [k for k in self.required_credentials if not self.credentials.get(k)]
        if missing:
            return HealthStatus(ok=False, message=f"Faltan credenciales: {', '.join(missing)}")
        return HealthStatus(ok=True, message="ok")


# --------------------------------------------------------------------- Imagen / vídeo


class ImageRequest(BaseModel):
    prompt: str
    search_query: str = ""
    negative_prompt: str | None = None
    width: int = 1080
    height: int = 1920
    style_tags: list[str] = Field(default_factory=list)
    seed: int | None = None
    exclude_hashes: list[str] = Field(default_factory=list)  # evita repetir recursos
    out_dir: Path


class ImageGenerationProvider(BaseProvider):
    category = ProviderCategory.IMAGE

    @abstractmethod
    def generate(self, request: ImageRequest) -> MediaAsset:
        """Devuelve una imagen (kind=image) de al menos width×height o recortable a 9:16."""


class VideoRequest(BaseModel):
    prompt: str
    search_query: str = ""
    duration_s: float = 4.0
    width: int = 1080
    height: int = 1920
    image_path: Path | None = None  # image-to-video
    exclude_hashes: list[str] = Field(default_factory=list)
    out_dir: Path


class VideoGenerationProvider(BaseProvider):
    category = ProviderCategory.VIDEO

    @abstractmethod
    def generate(self, request: VideoRequest) -> MediaAsset:
        """Devuelve un clip (kind=video) de duración >= duration_s o bucleable."""


# --------------------------------------------------------------------- Voz


class Voice(BaseModel):
    id: str
    name: str
    language: str
    gender: str | None = None
    style: str | None = None


class TTSRequest(BaseModel):
    text: str
    language: str = "es"
    voice_id: str | None = None
    speed: float = 1.0  # 1.0 = natural
    out_path: Path


class TextToSpeechProvider(BaseProvider):
    category = ProviderCategory.TTS

    @abstractmethod
    def list_voices(self, language: str | None = None) -> list[Voice]: ...

    @abstractmethod
    def synthesize(self, request: TTSRequest) -> MediaAsset:
        """Genera WAV/MP3 (kind=audio_voice) con duration_s rellenado."""


# --------------------------------------------------------------------- Música / SFX


class MusicRequest(BaseModel):
    mood: str
    genre: str | None = None
    duration_s: float
    bpm: int | None = None
    exclude_ids: list[str] = Field(default_factory=list)
    out_dir: Path


class MusicGenerationProvider(BaseProvider):
    category = ProviderCategory.MUSIC

    @abstractmethod
    def get_track(self, request: MusicRequest) -> MediaAsset:
        """Devuelve una pista (kind=audio_music) de duración >= duration_s (o bucleable)."""


class SFXRequest(BaseModel):
    effect: str  # "whoosh", "impact", "riser", "pop", "ambience:city", ...
    duration_s: float | None = None
    out_dir: Path


class SoundEffectsProvider(BaseProvider):
    category = ProviderCategory.SFX

    @abstractmethod
    def get_effect(self, request: SFXRequest) -> MediaAsset: ...


# --------------------------------------------------------------------- Subtítulos


class WordTiming(BaseModel):
    word: str
    start_s: float
    end_s: float


class SubtitleCue(BaseModel):
    start_s: float
    end_s: float
    text: str
    words: list[WordTiming] = Field(default_factory=list)


class SubtitleRequest(BaseModel):
    text: str
    audio_path: Path
    audio_duration_s: float
    language: str = "es"
    offset_s: float = 0.0  # inicio de la escena en la línea temporal
    max_chars_per_cue: int = 32


class SubtitleProvider(BaseProvider):
    category = ProviderCategory.SUBTITLE

    @abstractmethod
    def align(self, request: SubtitleRequest) -> list[SubtitleCue]: ...


# --------------------------------------------------------------------- Renderizado


class MediaProbe(BaseModel):
    path: str
    duration_s: float
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_audio: bool = False
    size_bytes: int = 0
    integrated_lufs: float | None = None
    true_peak_db: float | None = None
    black_segments: list[tuple[float, float]] = Field(default_factory=list)
    frozen_segments: list[tuple[float, float]] = Field(default_factory=list)
    silence_segments: list[tuple[float, float]] = Field(default_factory=list)


class SceneRenderSpec(BaseModel):
    scene_index: int
    visual_path: Path
    visual_kind: Literal["image", "video"]
    duration_s: float
    camera_motion: str = "slow_zoom_in"  # slow_zoom_in|zoom_out|pan_left|pan_right|pan_up|ken_burns|static
    shot_changes: int = 1  # sub-planos dentro de la escena para evitar estatismo
    on_screen_text: str | None = None
    width: int = 1080
    height: int = 1920
    fps: int = 30
    out_path: Path


class AssembleSpec(BaseModel):
    segments: list[Path]
    transitions: list[str]  # len = len(segments) - 1  ("cut", "fade", "slideleft", ...)
    transition_s: float = 0.3
    fps: int = 30
    out_path: Path


class AudioTrack(BaseModel):
    path: Path
    start_s: float = 0.0
    gain_db: float = 0.0
    role: Literal["voice", "music", "sfx"] = "voice"
    loop: bool = False
    fade_in_s: float = 0.0
    fade_out_s: float = 0.0


class AudioMixSpec(BaseModel):
    tracks: list[AudioTrack]
    duration_s: float
    duck_music_under_voice: bool = True
    target_lufs: float = -14.0
    true_peak_db: float = -1.0
    out_path: Path


class SubtitleStyle(BaseModel):
    font: str = "Inter"
    font_size: int = 72
    primary_color: str = "#FFFFFF"
    highlight_color: str = "#FFD400"
    outline_color: str = "#000000"
    outline: int = 5
    margin_v: int = 420  # px desde abajo (zona segura)
    margin_h: int = 90
    uppercase: bool = False
    karaoke: bool = True  # compatibilidad: equivale a mode="karaoke"
    # karaoke: frase con resaltado palabra a palabra · word_pop: una palabra grande cada vez ·
    # line: frase completa sin resaltado
    mode: Literal["karaoke", "word_pop", "line"] = "karaoke"


class EncodeProfile(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_codec: str = "libx264"
    video_bitrate: str = "8M"
    max_bitrate: str = "10M"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate: int = 48000
    pix_fmt: str = "yuv420p"
    container: str = "mp4"


class FinalizeSpec(BaseModel):
    video_path: Path
    audio_path: Path
    subtitles: list[SubtitleCue] = Field(default_factory=list)
    subtitle_style: SubtitleStyle | None = None  # None = sin subtítulos grabados
    profile: EncodeProfile = Field(default_factory=EncodeProfile)
    metadata: dict[str, str] = Field(default_factory=dict)
    draft: bool = False  # codificación rápida (previsualización para revisión)
    out_path: Path


class VideoRenderingProvider(BaseProvider):
    category = ProviderCategory.RENDERING

    @abstractmethod
    def render_scene(self, spec: SceneRenderSpec) -> MediaAsset: ...

    @abstractmethod
    def assemble(self, spec: AssembleSpec) -> MediaAsset: ...

    @abstractmethod
    def mix_audio(self, spec: AudioMixSpec) -> MediaAsset: ...

    @abstractmethod
    def finalize(self, spec: FinalizeSpec) -> MediaAsset: ...

    @abstractmethod
    def probe(self, path: Path, analyze: bool = False) -> MediaProbe: ...

    @abstractmethod
    def extract_frame(self, video: Path, at_s: float, out_path: Path) -> Path: ...


# --------------------------------------------------------------------- Almacenamiento


class StorageProvider(BaseProvider):
    category = ProviderCategory.STORAGE

    @abstractmethod
    def put(self, local_path: Path, key: str) -> str:
        """Guarda y devuelve un URI."""

    @abstractmethod
    def get(self, key: str, dest: Path) -> Path: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    def public_url(self, key: str) -> str | None:
        """URL pública (necesaria p. ej. para Instagram). None si no se admite."""
        return None


# --------------------------------------------------------------------- Publicación


class PublishRequest(BaseModel):
    platform: str
    video_path: Path
    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)
    thumbnail_path: Path | None = None
    privacy: Literal["private", "unlisted", "public"] = "private"
    authorization_id: str  # id de la autorización expresa del usuario


class PublishResult(BaseModel):
    platform: str
    status: Literal["published", "uploaded_private", "manual_package", "failed"]
    url: str | None = None
    external_id: str | None = None
    message: str = ""
    package_path: str | None = None


class PublishingProvider(BaseProvider):
    category = ProviderCategory.PUBLISHING
    platforms: ClassVar[list[str]] = []
    supports_direct_publish: ClassVar[bool] = False

    @abstractmethod
    def check_requirements(self, request: PublishRequest) -> list[str]:
        """Devuelve la lista de limitaciones/requisitos incumplidos (vacía = OK)."""

    @abstractmethod
    def publish(self, request: PublishRequest) -> PublishResult: ...


INTERFACE_BY_CATEGORY: dict[ProviderCategory, type[BaseProvider]] = {
    ProviderCategory.IMAGE: ImageGenerationProvider,
    ProviderCategory.VIDEO: VideoGenerationProvider,
    ProviderCategory.TTS: TextToSpeechProvider,
    ProviderCategory.MUSIC: MusicGenerationProvider,
    ProviderCategory.SFX: SoundEffectsProvider,
    ProviderCategory.SUBTITLE: SubtitleProvider,
    ProviderCategory.RENDERING: VideoRenderingProvider,
    ProviderCategory.STORAGE: StorageProvider,
    ProviderCategory.PUBLISHING: PublishingProvider,
}


class ProviderGateway(ABC):
    """Puerta única por la que los agentes usan proveedores.

    La implementación real (fase 4) aplica selección principal/alternativos, presupuesto,
    autorización de gasto y registro de costes. Los agentes no saben qué proveedor responde.
    """

    @abstractmethod
    def invoke(
        self,
        category: ProviderCategory,
        operation: str,
        request: Any,
        *,
        project_id: str | None = None,
        scene_index: int | None = None,
    ) -> Any: ...

    @abstractmethod
    def query(self, category: ProviderCategory, operation: str, *args: Any, project_id: str | None = None,
              **kwargs: Any) -> Any:
        """Operaciones sin coste (list_voices, probe, align...). `project_id` permite respetar
        el proveedor preferido del proyecto, igual que en `invoke`."""
