"""Composición y validación de títulos, descripciones y hashtags según cada plataforma.

Las plataformas miden distinto: YouTube cuenta la descripción en bytes UTF-8 y las etiquetas
con comillas si llevan espacios; TikTok mide el pie en unidades UTF-16; Instagram en caracteres
y limita los hashtags dentro del pie.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..providers.interfaces import SubtitleCue

from .platforms import MetadataLimits, PlatformProfile

_HASHTAG = re.compile(r"^#[^\s#]+$")


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def clean_hashtag(tag: str) -> str:
    tag = re.sub(r"[^\w#]", "", tag.strip().lstrip("#"), flags=re.UNICODE)
    return f"#{tag}" if tag else ""


def youtube_tags_length(tags: list[str]) -> int:
    """Suma de caracteres de las etiquetas: comas entre ellas y comillas en las que llevan espacios."""
    total = 0
    for t in tags:
        total += len(t) + (2 if " " in t else 0)
    return total + max(0, len(tags) - 1)


class PublishFields(BaseModel):
    """Campos listos para enviar a la plataforma (o pegar en la publicación manual)."""

    platform: str
    title: str | None = None
    description: str | None = None
    caption: str | None = None
    tags: list[str] = Field(default_factory=list)  # etiquetas (YouTube) sin '#'
    hashtags: list[str] = Field(default_factory=list)


def compose(profile: PlatformProfile, title: str, description: str, hashtags: list[str]) -> PublishFields:
    tags = [h for h in (clean_hashtag(x) for x in hashtags) if h]
    tag_line = " ".join(tags)
    m = profile.metadata
    if m.mode == "title_description":
        desc = f"{description.strip()}\n\n{tag_line}".strip()
        return PublishFields(platform=profile.id, title=title.strip(), description=desc, hashtags=tags,
                             tags=[t.lstrip("#") for t in tags])
    caption = f"{description.strip()}\n\n{tag_line}".strip() if description.strip() else tag_line
    if m.mode == "caption":
        return PublishFields(platform=profile.id, caption=caption, hashtags=tags, title=title.strip() or None)
    # title_caption: el campo `title` es el pie completo
    return PublishFields(platform=profile.id, title=caption, caption=caption, hashtags=tags)


def validate_fields(profile: PlatformProfile, fields: PublishFields) -> list[str]:
    m: MetadataLimits = profile.metadata
    issues: list[str] = []
    if m.mode == "title_description":
        title = fields.title or ""
        if m.title_required and not title:
            issues.append("el título es obligatorio")
        if len(title) > m.title_max_chars:
            issues.append(f"título de {len(title)} caracteres (máx {m.title_max_chars})")
        if "<" in title or ">" in title or "<" in (fields.description or "") or ">" in (fields.description or ""):
            issues.append("no se admiten los caracteres < ni >")
        nbytes = len((fields.description or "").encode("utf-8"))
        limit = m.description_max_bytes or m.description_max_chars
        if nbytes > limit:
            issues.append(f"descripción de {nbytes} bytes (máx {limit})")
        if m.tags_total_chars is not None and youtube_tags_length(fields.tags) > m.tags_total_chars:
            issues.append(f"etiquetas de {youtube_tags_length(fields.tags)} caracteres (máx {m.tags_total_chars})")
    else:
        text = fields.caption or ""
        measure = utf16_len(text) if m.caption_unit == "utf16" else len(text)
        limit = m.caption_max or m.description_max_chars
        if measure > limit:
            issues.append(f"pie de {measure} {'unidades UTF-16' if m.caption_unit == 'utf16' else 'caracteres'} (máx {limit})")
        mentions = len(re.findall(r"@\w+", text))
        if m.mentions_max is not None and mentions > m.mentions_max:
            issues.append(f"{mentions} menciones (máx {m.mentions_max})")
    if len(fields.hashtags) > m.hashtags_max:
        issues.append(f"{len(fields.hashtags)} hashtags (máx {m.hashtags_max})")
    if any(not _HASHTAG.match(h) for h in fields.hashtags):
        issues.append("hashtag con espacios o caracteres no válidos")
    return issues


def fit_hashtags(profile: PlatformProfile, title: str, description: str, hashtags: list[str]) -> PublishFields:
    """Compone y, si no cabe, recorta hashtags (los últimos primero) antes de rechazar el texto."""
    tags = [h for h in (clean_hashtag(x) for x in hashtags) if h][: profile.metadata.hashtags_max]
    fields = compose(profile, title, description, tags)
    while tags and validate_fields(profile, fields):
        tags = tags[:-1]
        fields = compose(profile, title, description, tags)
    return fields


def regroup_cues(cues: list[SubtitleCue], lines: list[str]) -> list[SubtitleCue]:
    """Reagrupa las palabras ya temporizadas según las líneas de subtítulo que escribió el guionista.

    Solo se aplica si las líneas contienen EXACTAMENTE las mismas palabras que el alineador (si no, se conservan
    los subtítulos originales): así se respetan los cortes pensados para la lectura sin arriesgar el texto.
    """
    words = [w for c in cues for w in c.words]
    expected = [w for line in lines for w in line.split()]
    if not lines or not words or [w.word for w in words] != expected:
        return cues
    out: list[SubtitleCue] = []
    i = 0
    for line in lines:
        n = len(line.split())
        chunk = words[i:i + n]
        i += n
        if chunk:
            out.append(SubtitleCue(start_s=chunk[0].start_s, end_s=chunk[-1].end_s,
                                   text=" ".join(w.word for w in chunk), words=chunk))
    return out
