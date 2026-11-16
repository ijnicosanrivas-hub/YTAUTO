"""Tema visual y de personalidad de los agentes (capa intercambiable).

Un tema solo cambia nombres, colores, frases y el tono de los campos explicativos.
No altera el contenido de los vídeos ni el flujo de producción. Se elige con `YTAUTO_THEME`
(por defecto `gotham`; `classic` desactiva los personajes).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .settings import REPO_ROOT

THEME_DIR = REPO_ROOT / "config" / "theme"
DEFAULT_THEME = "gotham"
QUOTE_STATES = ("idle", "started", "finished", "waiting", "error")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[a-z0-9_-]+$")


class Persona(BaseModel):
    character: str
    alias: str
    epithet: str
    alignment: str
    color: str
    glyph: str
    persona: str
    quotes: dict[str, str]


class Palette(BaseModel):
    accent: str
    background: str
    panel: str


class Theme(BaseModel):
    id: str
    name: str
    brand: str
    room_title: str
    room_subtitle: str
    palette: Palette
    agents: dict[str, Persona] = Field(default_factory=dict)

    def persona(self, agent: str) -> Persona | None:
        return self.agents.get(agent)

    def problems(self, agent_names: list[str]) -> list[str]:
        """Incoherencias del tema (vacío = válido). Un tema sin personajes es válido."""
        out: list[str] = []
        for hex_ in (self.palette.accent, self.palette.background, self.palette.panel):
            if not _HEX.match(hex_):
                out.append(f"color de paleta inválido: {hex_}")
        if not self.agents:
            return out
        missing = [n for n in agent_names if n not in self.agents]
        extra = [n for n in self.agents if n not in agent_names]
        if missing:
            out.append(f"faltan agentes: {missing}")
        if extra:
            out.append(f"agentes desconocidos: {extra}")
        for label, values in (("personaje", [p.character for p in self.agents.values()]),
                              ("color", [p.color.lower() for p in self.agents.values()])):
            if len(set(values)) != len(values):
                out.append(f"{label} repetido")
        for name, p in self.agents.items():
            if not _HEX.match(p.color):
                out.append(f"{name}: color inválido {p.color}")
            absent = [s for s in QUOTE_STATES if not p.quotes.get(s, "").strip()]
            if absent:
                out.append(f"{name}: faltan frases {absent}")
        return out


def load_theme(theme_id: str | None = None, directory: Path | None = None) -> Theme:
    """Carga el tema pedido; si no existe o es inválido vuelve a `classic` (nunca rompe la app)."""
    directory = directory or THEME_DIR
    wanted = (theme_id or os.environ.get("YTAUTO_THEME") or DEFAULT_THEME).strip().lower()
    for candidate in (wanted, "classic"):
        if not _ID.match(candidate):
            continue
        path = directory / f"{candidate}.yaml"
        if path.is_file():
            try:
                return Theme.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")))
            except Exception:  # noqa: BLE001 - tema roto: se usa el siguiente
                continue
    return Theme(id="classic", name="Clásico", brand="YTAUTO", room_title="Sala de producción",
                 room_subtitle="Fábrica multiagente de vídeos cortos",
                 palette=Palette(accent="#22d3ee", background="#0b1020", panel="#121a30"))


def available_themes(directory: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (directory or THEME_DIR).glob("*.yaml"))


BLOCK_START = "<!-- tema:inicio (generado por scripts/aplicar_tema.py; no editar a mano) -->"
BLOCK_END = "<!-- tema:fin -->"
_BLOCK_RE = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)


def prompt_block(p: Persona) -> str:
    """Párrafo de personalidad para el prompt de rol. Solo afecta al tono de los campos explicativos."""
    return (f"{BLOCK_START}\n"
            f"Personalidad (solo tono): en esta sala de producción interpretas a {p.character} ({p.epithet}). {p.persona}\n"
            "Esa personalidad se nota ÚNICAMENTE en los campos explicativos para el usuario (resúmenes, motivos, "
            "notas). El contenido del vídeo (títulos, concepto, estilo, guion, narración, subtítulos, prompts de "
            "imagen, textos de publicación) se crea EXACTAMENTE como si esta personalidad no existiera: no uses el "
            "nombre, los temas, el vocabulario ni los recursos del personaje (acertijos, chistes, monedas, Gotham...) "
            "salvo que la temática del usuario lo pida. No rompe el esquema JSON ni altera ningún dato técnico.\n"
            f"{BLOCK_END}\n")


def apply_to_prompt(text: str, persona: Persona | None) -> str:
    """Devuelve el texto del rol con el bloque de personaje actualizado (o sin él si no hay personaje)."""
    clean = _BLOCK_RE.sub("", text)
    if persona is None:
        return clean
    if not clean.startswith("---"):
        return clean
    head, sep, body = clean.partition("\n---\n")  # frontmatter | cuerpo
    if not sep:
        return clean
    return f"{head}{sep}{prompt_block(persona)}\n{body.lstrip(chr(10))}"
