"""Entrevista previa del director: antes de producir, pregunta lo necesario para pulir una idea abstracta.

Usa a Claude (a través de `LLMProvider`) para formular preguntas a medida de la idea. Si Claude no está
disponible, usa un cuestionario base que cubre lo imprescindible. Siempre incluye duración y calidad.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from ..core.models import MAX_DURATION_S, MIN_DURATION_S
from ..llm.base import LLMError, LLMProvider, LLMRequest


class BriefQuestion(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]{2,32}$")
    question: str = Field(min_length=5, max_length=240)
    kind: Literal["choice", "text"] = "text"
    options: list[str] = Field(default_factory=list, max_length=6)
    why: str = Field(default="", max_length=200)  # por qué lo pregunta (se muestra al usuario)


class BriefQuestions(BaseModel):
    reading: str = Field(default="", max_length=600)  # cómo ha entendido el director la idea en bruto
    questions: list[BriefQuestion] = Field(min_length=4, max_length=12)
    source: Literal["claude", "base"] = "claude"


BASE_QUESTIONS = [
    BriefQuestion(id="duration", kind="choice", question="¿Cuánto debe durar el vídeo?",
                  options=["45 s", "60 s", "75 s"], why="Define cuántas escenas y cuánto texto caben."),
    BriefQuestion(id="quality", kind="choice", question="¿Qué nivel de calidad y acabado quieres?",
                  options=["Máxima calidad (más lento)", "Equilibrado", "Rápido (borrador)"],
                  why="Más calidad = más revisiones y más uso de licencia."),
    BriefQuestion(id="goal", kind="choice", question="¿Qué quieres conseguir con este vídeo?",
                  options=["Informar", "Entretener", "Viralizar", "Vender o llevar tráfico", "Inspirar"],
                  why="El objetivo cambia el gancho y el cierre."),
    BriefQuestion(id="audience", kind="text", question="¿A quién va dirigido? (edad, intereses, nivel de conocimiento)",
                  why="Ajusta el vocabulario y las referencias."),
    BriefQuestion(id="tone", kind="choice", question="¿Qué tono prefieres?",
                  options=["Épico", "Divertido", "Serio / documental", "Misterio", "Emotivo"],
                  why="Marca la voz, la música y el ritmo."),
    BriefQuestion(id="hook_style", kind="choice", question="¿Cómo quieres que arranque (el gancho de los 2 primeros segundos)?",
                  options=["Pregunta intrigante", "Dato impactante", "Romper un mito", "Empezar en plena acción",
                           "Que lo proponga el director"],
                  why="El gancho decide si la gente se queda; luego elegirás entre 3 propuestas."),
    BriefQuestion(id="structure", kind="choice", question="¿Qué estructura encaja mejor?",
                  options=["Historia con giro final", "Top / lista con remate", "Mito vs realidad", "Antes y después",
                           "Explicación paso a paso", "Que la proponga el director"],
                  why="Ordena las escenas y dónde va la revelación."),
    BriefQuestion(id="visual_style", kind="choice", question="¿Qué estilo visual quieres?",
                  options=["Realista / cinematográfico", "Ilustrado / animado", "3D", "Figuras tipo LEGO",
                           "Collage con texto grande", "Que lo decida el director"],
                  why="Define las imágenes y los clips (y su coste en créditos)."),
    BriefQuestion(id="references", kind="text", question="¿Algún vídeo, canal o estilo de referencia que te guste?",
                  why="Copiamos el ritmo y el acabado, no el contenido."),
    BriefQuestion(id="must_have", kind="text", question="¿Qué no puede faltar? (datos, frases, escenas, nombres)",
                  why="Se incluirá sí o sí en el guion."),
    BriefQuestion(id="avoid", kind="text", question="¿Hay algo que debamos evitar?",
                  why="Temas, palabras o imágenes que no quieres."),
    BriefQuestion(id="ending", kind="text", question="¿Cómo debe terminar? ¿Qué quieres que haga quien lo vea?",
                  why="Define la llamada a la acción final."),
]

TASK = f"""Eres el director de producción y estratega de contenido de un canal de vídeos cortos verticales
(9:16, {MIN_DURATION_S}–{MAX_DURATION_S} s, Shorts / Reels / TikTok). El usuario te da una idea abstracta y sin pulir.
ANTES de producir, hazle entre 7 y 10 preguntas concretas para modelar el vídeo a su gusto: cada decisión que
tomes ahora evita correcciones (y créditos gastados) después. Reglas:
- Incluye SIEMPRE una pregunta con id "duration" (opciones en segundos entre {MIN_DURATION_S} y {MAX_DURATION_S}) y otra
  con id "quality" (nivel de calidad/acabado).
- Cubre las decisiones de diseño y estructura, a medida de ESTA idea y del canal: ángulo o giro que la haga
  irresistible, público, tipo de gancho (pregunta, dato impactante, romper un mito, en plena acción…), estructura
  (historia con giro, lista, mito vs realidad…), tono, estilo visual, referencias, datos imprescindibles, qué evitar y
  final o llamada a la acción. Nada genérico si puedes concretar (p. ej. opciones de ángulo pensadas para esta idea).
- Usa kind "choice" con 2–6 opciones cuando ayude a decidir rápido (incluye «que lo decida el director» si procede);
  "text" para respuestas abiertas.
- `reading`: en 1–3 frases, cómo has entendido la idea, qué ángulo ves con más potencial y qué dudas tienes.
- Escribe en español, frases cortas y claras. Los id en minúsculas con guiones bajos."""



def ask_briefing(llm: LLMProvider | None, model: str, idea: str, channel: str, call=None) -> BriefQuestions:
    """Preguntas del director. `call` permite atender la llamada con la licencia del canal."""
    if llm is not None and getattr(llm, "name", "") != "local_draft":
        request = LLMRequest(agent="director", model=model, task=TASK,
                             context={"idea": idea, "channel": channel},
                             output_schema=BriefQuestions.model_json_schema())
        try:
            response = (call or llm.complete)(request)
            out = BriefQuestions.model_validate({**response.data, "source": "claude"})
            return _ensure_core(out)
        except (LLMError, ValidationError, KeyError, ValueError):
            pass
    return BriefQuestions(reading=f"Idea recibida: «{idea.strip()[:200]}». Antes de empezar necesito concretar estos puntos.",
                          questions=BASE_QUESTIONS, source="base")


def _ensure_core(q: BriefQuestions) -> BriefQuestions:
    ids = {x.id for x in q.questions}
    extra = [b for b in BASE_QUESTIONS[:2] if b.id not in ids]
    q.questions = (extra + q.questions)[:12]
    return q


def duration_from_answer(answer: str) -> int | None:
    """«60 s», «unos 75 segundos» → 60/75 (dentro de los límites); None si no hay número válido."""
    for m in re.finditer(r"(\d{2,3})", answer or ""):
        v = int(m.group(1))
        if MIN_DURATION_S <= v <= MAX_DURATION_S:
            return v
    return None
