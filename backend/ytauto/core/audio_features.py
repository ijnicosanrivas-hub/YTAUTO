"""Capacidades de ElevenLabs que el agente de voz y el de sonido pueden usar, y utilidades de etiquetas y tiempos.

Datos de la documentación y la página de precios oficiales de ElevenLabs (noviembre de 2026):
- Eleven v4 (`eleven_v4`): su modelo más expresivo; admite etiquetas de audio (`[whispers]`, `[sighs]`, `[excited]`…)
  y se usa a través de la API Text to Dialogue. v4 y v3 NO admiten SSML (`<break>`): las pausas se marcan con
  puntos suspensivos y etiquetas. Coste por API: 1 crédito por carácter (Turbo/Flash: 0,5).
- Text to Dialogue (`/v1/text-to-dialogue/with-timestamps`): varias voces (hasta 10) en una generación, ≤ 2.000
  caracteres por petición, con tiempos por carácter → subtítulos palabra a palabra exactos.
- Efectos de sonido (`/v1/sound-generation`): 200 créditos por efecto con duración automática o 40 por segundo con
  duración fija (0,5–30 s).
- Voice Design (`/v1/text-to-voice/design` + `/v1/text-to-voice`): voces nuevas a partir de una descripción.
- Voice Changer (`/v1/voice-changer/{voice_id}`): tu grabación → la voz del canal conservando la interpretación;
  1.000 créditos por minuto.
- Actor Mode y el montaje multipista de Studio son funciones de la web de ElevenLabs (no tienen API): en YTAUTO
  el montaje multipista lo hace la propia app (voz, música y efectos con FFmpeg) y el equivalente de Actor Mode es
  el Voice Changer.
- Planes: Starter añade licencia comercial y clonación instantánea; Creator añade Professional Voice Cloning
  (se crea en la web de ElevenLabs y luego se elige aquí como voz).
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

TIER_ORDER = ["free", "starter", "creator", "pro", "scale", "business", "enterprise"]


class AudioFeature(BaseModel):
    id: str
    title: str
    question: str          # cómo se le pregunta al usuario
    what: str              # qué hace, en una frase
    cost: str              # coste en créditos (dato oficial)
    min_tier: str = "free"
    in_app: bool = True    # False = solo en la web de ElevenLabs (se explica cómo encaja)
    per_video: bool = True  # se puede activar/desactivar en cada vídeo
    default: bool = False


FEATURES: list[AudioFeature] = [
    AudioFeature(id="expressive", title="Interpretación emocional (Eleven v4)",
                 question="¿Quieres que la voz interprete cada frase (susurros, tensión, sorpresa, pausas antes de revelar)?",
                 what="El agente de voz marca cada frase con etiquetas de emoción y la narra con Eleven v4.",
                 cost="1 crédito por carácter (como la voz normal)", default=True),
    AudioFeature(id="word_timing", title="Subtítulos palabra a palabra exactos",
                 question="¿Quieres subtítulos que resalten cada palabra justo cuando se pronuncia?",
                 what="Usa los tiempos que devuelve ElevenLabs con el audio para sincronizar cada palabra.",
                 cost="Sin coste extra (viene con la propia locución)", default=True),
    AudioFeature(id="dialogue", title="Diálogos con varias voces",
                 question="¿Quieres que en algunos vídeos hablen varios personajes con voces distintas?",
                 what="Narrador, protagonista, testigo… en una sola generación con Text to Dialogue (hasta 10 voces).",
                 cost="1 crédito por carácter"),
    AudioFeature(id="sfx", title="Efectos de sonido generados por IA",
                 question="¿Quieres efectos creados a medida de lo que se cuenta (pasos, puertas, tormenta, estática…)?",
                 what="El agente de sonido pide cada efecto descrito en el guion a ElevenLabs.",
                 cost="200 créditos por efecto (o 40 por segundo con duración fija)"),
    AudioFeature(id="voice_cast", title="Voces propias para cada canal", per_video=False,
                 question="¿Quieres una identidad sonora por canal (narrador reconocible, antagonista, voz documental…)?",
                 what="Asignas una voz a cada papel en cada canal; los vídeos del canal la usan siempre.",
                 cost="Sin coste (eliges voces de tu biblioteca)", default=True),
    AudioFeature(id="voice_design", title="Diseñar voces con una descripción", per_video=False,
                 question="¿Quieres crear voces nuevas describiéndolas (p. ej. «narrador grave de documental, misterioso»)?",
                 what="Voice Design genera 3 muestras; eliges una y queda en tu biblioteca y en el reparto del canal.",
                 cost="ElevenLabs indica el coste al generar las muestras"),
    AudioFeature(id="voice_changer", title="Tu interpretación, con la voz del canal (Voice Changer)",
                 question="¿Quieres grabar tú alguna frase con la emoción exacta y que suene con la voz del canal?",
                 what="Subes tu grabación de una escena y ElevenLabs la convierte en la voz elegida, con tu ritmo y emoción.",
                 cost="1.000 créditos por minuto de audio", min_tier="starter"),
    AudioFeature(id="pro_clone", title="Clonación profesional de voz (PVC)", per_video=False, in_app=False,
                 question="¿Quieres clonar una voz real (la tuya o de un locutor con permiso) con calidad profesional?",
                 what="Se crea en la web de ElevenLabs (grabaciones + verificación); después aparece aquí para elegirla.",
                 cost="Incluida en tu plan Creator", min_tier="creator"),
    AudioFeature(id="studio", title="Montaje multipista y Actor Mode (Studio)", per_video=False, in_app=False,
                 question="Montaje multipista y Actor Mode",
                 what="El montaje de voz, música, efectos y vídeo ya lo hace YTAUTO en tu PC; Actor Mode solo existe en "
                      "la web de Studio y aquí su equivalente es el Voice Changer.",
                 cost="—"),
]
FEATURE_IDS = {f.id for f in FEATURES}
PER_VIDEO = [f.id for f in FEATURES if f.in_app and f.per_video]
DEFAULT_FEATURES = [f.id for f in FEATURES if f.default]

# Papeles del reparto de voces de cada canal.
ROLES = {"narrador": "Narrador principal", "protagonista": "Protagonista", "antagonista": "Antagonista",
         "secundario": "Personaje secundario / testigo", "documental": "Presentador documental"}

# Etiquetas que el agente de voz puede usar (las documentadas por ElevenLabs para v4 + otras descriptivas).
AUDIO_TAGS = ["[whispers]", "[sighs]", "[exhales]", "[laughs]", "[excited]", "[curious]", "[sarcastic]",
              "[mischievously]", "[crying]", "[shouting]", "[nervous, trembling voice]", "[angry]", "[surprised]",
              "[in disbelief]", "[serious tone]", "[slowly, building tension]", "[quietly]", "[dramatic pause]"]

_TAG = re.compile(r"\[[^\[\]]{1,60}\]")


def tier_allows(tier: str | None, min_tier: str) -> bool | None:
    """¿El plan cubre la función? None si no se sabe el plan."""
    if not tier:
        return None
    t = tier.lower()
    if t not in TIER_ORDER:
        return None
    return TIER_ORDER.index(t) >= TIER_ORDER.index(min_tier)


def feature_view(enabled: list[str], tier: str | None) -> list[dict[str, Any]]:
    return [{**f.model_dump(), "enabled": f.id in enabled, "plan_ok": tier_allows(tier, f.min_tier)} for f in FEATURES]


def strip_tags(text: str) -> str:
    """Texto sin etiquetas de audio (para subtítulos y para voces que no las entienden)."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def same_words(plain: str, performed: str) -> bool:
    """La interpretación solo añade etiquetas, pausas o énfasis: las palabras deben ser las mismas."""
    a = [_norm(w) for w in plain.split() if _norm(w)]
    b = [_norm(w) for w in strip_tags(performed).split() if _norm(w)]
    return a == b


def words_from_alignment(alignment: dict[str, Any] | None, offset_s: float = 0.0) -> list[dict[str, float | str]]:
    """Palabras con su inicio y fin a partir de los tiempos por carácter de ElevenLabs (sin las etiquetas)."""
    if not alignment:
        return []
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    words: list[dict[str, float | str]] = []
    cur, w_start, w_end, depth = "", 0.0, 0.0, 0
    for ch, s, e in zip(chars, starts, ends):
        if ch == "[":
            depth += 1
        if depth:
            if ch == "]":
                depth -= 1
            if cur:
                words.append({"word": cur, "start_s": w_start + offset_s, "end_s": w_end + offset_s})
                cur = ""
            continue
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start_s": w_start + offset_s, "end_s": w_end + offset_s})
                cur = ""
            continue
        if not cur:
            w_start = float(s)
        cur += ch
        w_end = float(e)
    if cur:
        words.append({"word": cur, "start_s": w_start + offset_s, "end_s": w_end + offset_s})
    return [w for w in words if _norm(str(w["word"]))]


def map_to_plain(plain: str, timed: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Pone los tiempos de las palabras interpretadas (con MAYÚSCULAS o «…») sobre las palabras del guion."""
    tokens = plain.split()
    keep = [t for t in tokens if _norm(t)]
    if len(keep) != len(timed) or any(_norm(a) != _norm(str(b["word"])) for a, b in zip(keep, timed)):
        return None
    out, i = [], 0
    for tok in tokens:
        if not _norm(tok):
            continue
        out.append({**timed[i], "word": tok})
        i += 1
    return out


_DIALOGUE = re.compile(r"^\s*([^:]{1,30}):\s*(.+)$")


def parse_dialogue(lines: list[str]) -> list[tuple[str, str]]:
    """«Testigo: Yo no vi nada» → ("testigo", "Yo no vi nada"). Las líneas sin papel se ignoran."""
    out = []
    for line in lines or []:
        m = _DIALOGUE.match(line or "")
        if m and m.group(2).strip():
            role = re.sub(r"[^a-záéíóúñü ]", "", m.group(1).strip().lower()).strip()
            out.append((role, m.group(2).strip()))
    return out


def role_voice(role: str, cast: dict[str, str]) -> str | None:
    """Voz de un papel; los nombres libres («testigo», «policía») caen en «secundario»."""
    if role in cast:
        return cast[role]
    for key in ("secundario", "protagonista", "narrador"):
        if cast.get(key):
            return cast[key]
    return None
