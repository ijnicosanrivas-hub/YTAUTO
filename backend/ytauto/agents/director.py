"""Agente 2 — Director de producción especializado en vídeo corto vertical."""
from __future__ import annotations

from ..core.models import CreativeBrief, Section
from .base import Agent, AgentContext, AgentResult

SECTION_ORDER = list(Section)
MIN_SCENE_S = 1.5
MAX_SCENE_S = 10.0


def check_brief(brief: CreativeBrief, target_s: float, hook_max_s: float) -> list[str]:
    issues: list[str] = []
    n = len(brief.scenes)
    if not 5 <= n <= 16:
        issues.append(f"Debe haber entre 5 y 16 escenas (hay {n})")
    if [s.index for s in brief.scenes] != list(range(n)):
        issues.append("Los índices de escena deben ser 0..n-1 consecutivos")
    total = sum(s.duration_s for s in brief.scenes)
    if abs(total - target_s) > 2.0:
        issues.append(f"La suma de duraciones ({total:.1f}s) debe ser {target_s}s ±2s")
    if brief.scenes and brief.scenes[0].section is not Section.HOOK:
        issues.append("La primera escena debe ser el gancho (section=hook)")
    if brief.scenes and brief.scenes[0].duration_s > hook_max_s + 0.01:
        issues.append(f"El gancho debe durar como máximo {hook_max_s}s")
    if not any(s.section is Section.CLOSING for s in brief.scenes):
        issues.append("Falta una escena de cierre (section=closing)")
    order = [SECTION_ORDER.index(s.section) for s in brief.scenes]
    if order != sorted(order):
        issues.append("Las secciones deben seguir el orden hook→context→development→climax→closing")
    for s in brief.scenes:
        if not MIN_SCENE_S <= s.duration_s <= MAX_SCENE_S:
            issues.append(f"Escena {s.index}: duración {s.duration_s}s fuera de [{MIN_SCENE_S}, {MAX_SCENE_S}]")
        if not s.visual_direction.strip():
            issues.append(f"Escena {s.index}: falta dirección visual")
    return issues


def normalize_durations(brief: CreativeBrief, target_s: float) -> CreativeBrief:
    """Ajusta proporcionalmente para que la suma sea exactamente la duración objetivo."""
    hook = brief.scenes[0]
    rest = brief.scenes[1:]
    rest_total = sum(s.duration_s for s in rest)
    factor = (target_s - hook.duration_s) / rest_total if rest_total else 1.0
    for s in rest:
        s.duration_s = round(s.duration_s * factor, 2)
    drift = round(target_s - sum(s.duration_s for s in brief.scenes), 2)
    brief.scenes[-1].duration_s = round(brief.scenes[-1].duration_s + drift, 2)
    brief.target_duration_s = int(target_s)
    return brief


TASK = """Eres el director de producción de una fábrica de vídeos cortos verticales (9:16) para
Reels, Shorts y TikTok. Diseña el plan creativo del vídeo a partir de la idea del usuario.

Requisitos:
- Si `user_request.brief` tiene preguntas y respuestas, son lo que el usuario te contestó antes de empezar:
  respétalas (duración, calidad, tono, público, ideas obligatorias o prohibidas) por encima de tus preferencias.
- Prioriza claridad, atractivo visual y retención desde el primer segundo, sin sacrificar calidad.
- Usa como referencia el reparto de secciones `section_slots` (puedes ajustarlo si la historia lo
  pide, manteniendo el orden hook→context→development→climax→closing).
- La escena 0 es el gancho y dura como máximo `hook_max_s` segundos.
- La suma de duraciones debe ser `target_duration_s`.
- Ritmo: con intensidad `intensity`, ningún plano debe quedar estático más de `max_static_shot_s` s
  (el editor subdividirá planos, pero diseña cambios visuales frecuentes).
- camera_motion ∈ slow_zoom_in, zoom_out, pan_left, pan_right, pan_up, tilt_down, ken_burns, punch_in,
  drift, static. Usa punch_in para golpes de efecto (gancho, revelación) y varía los movimientos.
- transition ∈ cut, fade, slideleft, slideright, slideup, wipeleft, zoomin, circleopen.
- Describe en visual_direction lo que debe verse, siempre pensado en vertical.
- Si el usuario no indicó estilo/tono/música, decide tú lo más adecuado al tema.
"""


class DirectorAgent(Agent):
    name = "director"
    title = "Director de producción"
    phases = frozenset({"creative_direction"})
    uses_claude = True

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        spec = ctx.spec
        tpl = ctx.narrative
        slots = tpl.allocate(spec.duration_s)
        context = {
            "user_request": spec.model_dump(mode="json", include={
                "name", "topic", "idea", "visual_style", "narration_type", "language",
                "voice_type", "music", "intensity", "mode", "brief",
            }),
            "target_duration_s": spec.duration_s,
            "section_slots": [s.model_dump(mode="json") | {"duration_s": s.duration_s} for s in slots],
            "hook_max_s": tpl.hook_max_s,
            "max_static_shot_s": tpl.max_static_shot_s[spec.intensity],
            "words_per_second": tpl.wps(spec.language),
        }
        brief = self.ask_llm(
            ctx, phase=phase, task=TASK, context=context, output_model=CreativeBrief,
            accept=lambda b: check_brief(b, spec.duration_s, tpl.hook_max_s),
        )
        brief = normalize_durations(brief, spec.duration_s)
        path = ctx.workspace.save("planning", "creative_brief", brief)
        ctx.memory.add_decision(self.name, f"Concepto: {brief.concept} | tono: {brief.tone} | estilo: {brief.visual_style}")
        return AgentResult(
            summary=f"Plan creativo: {len(brief.scenes)} escenas, {brief.target_duration_s}s, estilo '{brief.visual_style}'",
            artifacts={"creative_brief": str(path)},
            metrics={"scenes": len(brief.scenes)},
        )
