"""Agente 2 — Director de producción especializado en vídeo corto vertical."""
from __future__ import annotations

from ..core.models import HOOK_STYLES, CreativeBrief, Section
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


def check_viral(brief: CreativeBrief, target_s: float, hook_max_words: int) -> list[str]:
    """Criterios del «motor de vídeos virales»: solo lo imprescindible para que el usuario pueda elegir bien."""
    issues: list[str] = []
    hooks = brief.hook_options
    if len(hooks) < 3:
        issues.append("hook_options: propón 3 ganchos distintos para que el usuario elija")
    elif len({h.style for h in hooks}) < 3:
        issues.append(f"hook_options: los ganchos deben ser de tipos distintos ({', '.join(HOOK_STYLES)})")
    for i, h in enumerate(hooks):
        if len(h.text.split()) > hook_max_words * 1.3 + 1:
            issues.append(f"hook_options[{i}]: {len(h.text.split())} palabras; en el gancho caben unas {hook_max_words}")
        if h.on_screen_text and len(h.on_screen_text.split()) > 6:
            issues.append(f"hook_options[{i}]: el texto en pantalla debe tener 6 palabras como máximo")
        if not h.why.strip():
            issues.append(f"hook_options[{i}]: explica en `why` por qué detiene el scroll")
    if not brief.viral_angle.strip():
        issues.append("Falta viral_angle: por qué esta idea atrae y retiene")
    if len(brief.retention_plan) < 3:
        issues.append("retention_plan: coloca al menos 3 técnicas de retención con su segundo")
    elif not any(b.at_s <= target_s * 0.4 for b in brief.retention_plan):
        issues.append("retention_plan: pon al menos un bucle abierto o re-gancho en el primer 40 % del vídeo")
    if any(b.at_s > target_s for b in brief.retention_plan):
        issues.append("retention_plan: hay técnicas colocadas después del final del vídeo")
    if not brief.cta.strip():
        issues.append("Falta la llamada a la acción (cta)")
    if len(brief.title_options) < 3:
        issues.append("title_options: propón 3 títulos")
    if not brief.cover_concept.strip():
        issues.append("Falta cover_concept (portada)")
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


TASK = """Eres el director de producción y estratega de contenido (nivel top 1 %) de una fábrica de vídeos cortos
verticales (9:16) para Shorts, Reels y TikTok. Tu trabajo: convertir la idea del usuario en un vídeo con alta
retención y alto CTR, y explicar por qué funcionará. Diseña el plan creativo completo.

Prioridad absoluta — lo que el usuario contestó (`user_request.brief`) y sus notas (`corrections`): duración,
calidad, tono, público, estilo visual, referencias, ideas obligatorias o prohibidas. Eso manda sobre tus gustos.

Estrategia (rellena TODOS estos campos):
- `viral_angle`: por qué alguien se detendría y se quedaría hasta el final (curiosidad, emoción, utilidad,
  identidad, polémica sana). Concreto, no genérico. `target_viewer`: quién es y qué quiere sentir o saber.
- `hook_options`: 3 ganchos de tipos DISTINTOS (style ∈ pregunta, dato_impactante, contradiccion, in_medias_res,
  promesa, visual_sorpresa, historia_personal, reto). Cada uno: `text` = primeras palabras que se oyen (caben en
  `hook_max_s` segundos, sin saludos ni «en este vídeo»), `on_screen_text` ≤ 6 palabras, `visual` = qué se ve en el
  primer segundo (movimiento o imagen inesperada), `why` = por qué detiene el scroll. `chosen_hook` = tu favorito.
- `story_structure`: estructura y por qué encaja (p. ej. problema → giro → revelación; mito vs realidad;
  cuenta atrás con remate; antes/después). `opening_scene`: los 3 primeros segundos exactos.
- `retention_plan` (≥ 3, con su segundo `at_s`): bucle abierto en los primeros segundos que se resuelve al final
  (70-90 % del vídeo), re-ganchos cada 8-12 s (cambio visual, giro, «pero eso no es lo más raro»), revelación y,
  si encaja, cierre en bucle que conecte con el principio para que se vuelva a ver.
- `cta`: llamada a la acción natural ligada al contenido (comentar algo concreto, seguir para la parte 2…),
  nunca al principio. `title_options`: 3 títulos (curiosidad + especificidad, ≤ 60 caracteres, sin engañar).
  `cover_concept`: portada legible en móvil (fotograma, 2-4 palabras grandes, contraste).
- `risks`: dónde podría deslizar el espectador y cómo lo evitas.

Plan de escenas:
- Usa como referencia `section_slots` (puedes ajustarlo manteniendo el orden hook→context→development→climax→closing).
- La escena 0 es el gancho elegido y dura como máximo `hook_max_s` segundos. La suma de duraciones = `target_duration_s`.
- Valor nuevo en cada escena, nada de relleno. Con intensidad `intensity`, ningún plano estático más de
  `max_static_shot_s` s: diseña cambios visuales frecuentes.
- camera_motion ∈ slow_zoom_in, zoom_out, pan_left, pan_right, pan_up, tilt_down, ken_burns, punch_in, drift, static.
  Usa punch_in en golpes de efecto (gancho, revelación) y varía los movimientos.
- transition ∈ cut, fade, slideleft, slideright, slideup, wipeleft, zoomin, circleopen.
- visual_direction: lo que debe verse, siempre pensado en vertical y coherente con el estilo pedido.
- Si el usuario no indicó estilo/tono/música, decide tú lo más adecuado al tema y al canal (`channel`).
- Nada de clickbait engañoso: el vídeo debe cumplir lo que promete el gancho.
"""


def _channel_info(channel_id: str) -> dict:
    try:
        from ..core.channels import channels
        ch = next((c for c in channels() if c.id == channel_id), None)
        return {"id": channel_id, "name": ch.name, "tagline": ch.tagline} if ch else {"id": channel_id}
    except Exception:  # noqa: BLE001 - la información del canal es orientativa
        return {"id": channel_id}


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
            "channel": _channel_info(spec.channel),
        }
        mine = [c.model_dump(mode="json") for c in ctx.corrections if c.target_agent in (self.name, "chief")]
        task = TASK
        if mine:
            # El usuario rechazó el concepto (o el revisor pidió replantearlo): se rehace con sus indicaciones.
            context["corrections"] = mine
            if ctx.workspace.has("planning", "creative_brief"):
                context["previous_brief"] = ctx.workspace.load("planning", "creative_brief")
            task += ("\nHay indicaciones (`corrections`) sobre el plan anterior (`previous_brief`): aplícalas y conserva "
                     "lo que funcionaba.")
        hook_words = tpl.max_words(tpl.hook_max_s, spec.language)
        brief = self.ask_llm(
            ctx, phase=phase, task=task, context=context, output_model=CreativeBrief,
            accept=lambda b: check_brief(b, spec.duration_s, tpl.hook_max_s)
            + check_viral(b, spec.duration_s, hook_words),
        )
        if brief.hook_options:
            brief.chosen_hook = min(brief.chosen_hook, len(brief.hook_options) - 1)
        brief = normalize_durations(brief, spec.duration_s)
        path = ctx.workspace.save("planning", "creative_brief", brief)
        ctx.memory.add_decision(self.name, f"Concepto: {brief.concept} | tono: {brief.tone} | estilo: {brief.visual_style}"
                                           f" | ángulo: {brief.viral_angle[:120]}")
        hook = brief.hook()
        return AgentResult(
            summary=f"Plan creativo: {len(brief.scenes)} escenas, {brief.target_duration_s}s, estilo '{brief.visual_style}'"
                    + (f". Gancho propuesto: «{hook.text[:70]}» (+{len(brief.hook_options) - 1} alternativas)" if hook else ""),
            artifacts={"creative_brief": str(path)},
            metrics={"scenes": len(brief.scenes)},
        )
