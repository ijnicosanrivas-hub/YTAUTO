"""Estructura narrativa para vídeos cortos y cálculo de extensión de texto."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from .models import Section

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "config" / "narrative" / "default.yaml"


class SectionSlot(BaseModel):
    section: Section
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 2)


class NarrativeTemplate(BaseModel):
    name: str
    # Fracciones de la duración total por sección (deben sumar 1).
    fractions: dict[Section, float]
    hook_max_s: float = 3.0
    words_per_second: dict[str, float]  # por idioma
    pause_overhead: float = 0.08  # fracción del tiempo reservada a pausas/silencios
    min_speech_coverage: float = 0.8  # la narración debe cubrir al menos este % de la duración
    max_static_shot_s: dict[str, float]  # por intensidad

    @classmethod
    def load(cls, path: Path | None = None) -> "NarrativeTemplate":
        data = yaml.safe_load(Path(path or DEFAULT_TEMPLATE_PATH).read_text(encoding="utf-8"))
        return cls(**data)

    def allocate(self, duration_s: float) -> list[SectionSlot]:
        """Reparte la duración total entre secciones, respetando el gancho máximo."""
        total = sum(self.fractions.values())
        slots: list[SectionSlot] = []
        cursor = 0.0
        order = list(Section)
        for i, section in enumerate(order):
            frac = self.fractions.get(section, 0.0) / total
            length = duration_s * frac
            if section is Section.HOOK:
                length = min(length, self.hook_max_s)
            end = duration_s if i == len(order) - 1 else cursor + length
            slots.append(SectionSlot(section=section, start_s=round(cursor, 2), end_s=round(end, 2)))
            cursor = end
        return slots

    def wps(self, language: str) -> float:
        return self.words_per_second.get(language, self.words_per_second.get("default", 2.5))

    def max_words(self, duration_s: float, language: str) -> int:
        """Palabras máximas que caben con una narración realista (incluye pausas)."""
        speaking_time = duration_s * (1 - self.pause_overhead)
        return int(speaking_time * self.wps(language))

    def estimate_speech_s(self, text: str, language: str) -> float:
        words = len(text.split())
        return round(words / self.wps(language) / (1 - self.pause_overhead), 2)
