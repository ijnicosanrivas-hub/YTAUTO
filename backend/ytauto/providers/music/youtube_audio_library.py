"""Música de la Biblioteca de audio de YouTube Studio (descargada por el usuario e importada en YTAUTO).

Hechos oficiales (Ayuda de YouTube, «Use music and sound effects from the Audio Library», 2026):
- La Biblioteca de audio está solo en YouTube Studio (youtube.com/audiolibrary); cada pista se descarga a mano en MP3
  con el botón «Download». No hay API: YTAUTO no entra en tu cuenta ni descarga nada por su cuenta.
- La música es «copyright-safe»: Content ID no la reclama y se puede monetizar en el Programa para Partners.
- Las pistas con licencia Creative Commons exigen acreditar al artista en la descripción del vídeo (el texto se copia
  desde la columna «License type»). Las de licencia estándar de la biblioteca no lo exigen.
- YouTube NO da garantías sobre el uso fuera de la plataforma («can't give legal guidance, including guidance on issues
  with music that can occur off the platform»): por eso los paquetes de TikTok e Instagram llevan un aviso.

Las pistas viven en `library/youtube_audio_library/` (fuera de `library/music`, para que la música automática no las
use sin que se pidan) con un `.json` al lado: título, artista, género, estado de ánimo y licencia.
Se registra la última de la cadena (detrás de la música procedural), así que solo suena cuando el vídeo la elige.
"""
from __future__ import annotations

from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..interfaces import HealthStatus, MusicGenerationProvider, MusicRequest
from ..library import AUDIO_EXT, LibraryItem, default_library_root, scan, tokens

FOLDER = "youtube_audio_library"
AUDIO_LIBRARY_URL = "https://www.youtube.com/audiolibrary"
HELP_URL = "https://support.google.com/youtube/answer/3376882"
# Filtros de la Biblioteca de audio (pestaña Música).
GENRES = ["Ambient", "Children's", "Cinematic", "Classical", "Country & Folk", "Dance & Electronic", "Hip Hop & Rap",
          "Holiday", "Jazz & Blues", "Pop", "R&B & Soul", "Reggae", "Rock"]
MOODS = ["Angry", "Bright", "Calm", "Dark", "Dramatic", "Funky", "Happy", "Inspirational", "Romantic", "Sad"]
# Lo que piden el director y el guionista (en español o inglés) → estados de ánimo de la biblioteca.
MOOD_WORDS: dict[str, list[str]] = {
    "dark": ["tenso", "tensa", "tension", "suspense", "misterio", "misteriosa", "oscuro", "oscura", "noir", "terror",
             "miedo", "thriller", "inquietante", "tense", "mystery", "dark"],
    "dramatic": ["epico", "epica", "epic", "dramatico", "dramatica", "intenso", "intensa", "climax", "batalla",
                 "trailer", "cinematico", "cinematica", "dramatic", "heroico", "heroica"],
    "inspirational": ["inspirador", "inspiradora", "motivador", "motivadora", "emotivo", "superacion", "esperanza",
                      "inspirational", "uplifting", "triunfo", "victoria"],
    "happy": ["alegre", "feliz", "divertido", "divertida", "infantil", "ninos", "kids", "juego", "fiesta", "happy",
              "jugueton", "juguetona", "fun"],
    "bright": ["luminoso", "luminosa", "optimista", "fresco", "fresca", "positivo", "positiva", "bright", "verano"],
    "calm": ["tranquilo", "tranquila", "calma", "relajado", "relajada", "suave", "ambiente", "lofi", "calm", "chill",
             "reflexivo", "reflexiva"],
    "funky": ["energico", "energica", "ritmico", "ritmica", "groove", "urbano", "urbana", "deporte", "deportes",
              "accion", "funky", "hype", "trap"],
    "sad": ["triste", "melancolico", "melancolica", "nostalgico", "nostalgica", "drama", "sad"],
    "angry": ["agresivo", "agresiva", "rabia", "furia", "metal", "angry", "duro", "dura"],
    "romantic": ["romantico", "romantica", "amor", "romantic"],
}


def library_folder(root: Path | None = None) -> Path:
    return (root or default_library_root()) / FOLDER


def expand_query(text: str) -> set[str]:
    """Palabras de la petición + los estados de ánimo de la biblioteca que les corresponden."""
    words = tokens(text)
    out = set(words)
    for mood, syn in MOOD_WORDS.items():
        if words & set(syn) or mood in words:
            out.add(mood)
    return out


def attribution_required(meta: dict) -> bool:
    if "attribution_required" in meta:
        return bool(meta["attribution_required"])
    return str(meta.get("license", "")).lower().startswith(("cc", "creative commons"))


class YouTubeAudioLibraryMusicProvider(MusicGenerationProvider):
    """Pistas de la Biblioteca de audio de YouTube Studio importadas por el usuario."""
    name = "youtube_audio_library"
    display_name = "Biblioteca de audio de YouTube Studio"
    default_priority = 95  # detrás de la procedural: solo se usa cuando el vídeo la pide
    default_params = {"root": ""}

    def capabilities(self):
        return {"moods": MOODS, "genres": GENRES, "cost": 0, "copyright_safe_on": ["youtube_shorts"],
                "note": "Segura en YouTube; YouTube no garantiza el uso fuera de su plataforma."}

    @property
    def folder(self) -> Path:
        return library_folder(Path(self.params["root"]) if self.params.get("root") else None)

    def items(self) -> list[LibraryItem]:
        return scan(self.folder, AUDIO_EXT)

    def health_check(self) -> HealthStatus:
        n = len(self.items())
        return HealthStatus(ok=n > 0, message=f"{n} pistas de YouTube Studio" if n else
                            "Aún no has importado pistas de la Biblioteca de audio de YouTube Studio")

    def get_track(self, request: MusicRequest) -> MediaAsset:
        items = [i for i in self.items() if str(i.path.name) not in set(request.exclude_ids)]
        if not items:
            raise ProviderError(self.name, "No hay pistas importadas de la Biblioteca de audio de YouTube Studio "
                                           "(Recursos → Música de YouTube)", transient=False)
        query = expand_query(f"{request.mood} {request.genre or ''}")

        def score(i: LibraryItem) -> tuple[int, float, str]:
            tags = i.tags | tokens(f"{i.meta.get('genre', '')} {i.meta.get('mood', '')}")
            dur = float(i.meta.get("duration_s") or 0)
            # Mejor coincidencia de ánimo; a igualdad, la que cubre la duración sin repetirse.
            return (-len(tags & query), 0.0 if dur >= request.duration_s else 1.0, i.path.name)
        item = sorted(items, key=score)[0]
        meta = item.meta
        required = attribution_required(meta)
        from .local import audio_duration
        return MediaAsset(
            kind=AssetKind.AUDIO_MUSIC, path=str(item.path), duration_s=audio_duration(item.path), provider=self.name,
            sha256=sha256_file(item.path), source_url=AUDIO_LIBRARY_URL,
            license=License(name=str(meta.get("license") or "YouTube Audio Library"),
                            attribution=meta.get("attribution") if required else None, url=HELP_URL,
                            commercial_use=True),
            metadata={"title": meta.get("title"), "artist": meta.get("artist"), "genre": meta.get("genre"),
                      "mood": meta.get("mood"), "attribution_required": required, "file": item.path.name,
                      "source": "youtube_audio_library"})
