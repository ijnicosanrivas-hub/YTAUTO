"""Agente 3 — Guionista."""
from __future__ import annotations

import re

from ..core.models import CreativeBrief, Script
from ..core.narrative import NarrativeTemplate
from .base import Agent, AgentContext, AgentResult


def _sentences(text: str) -> list[str]:
    return [s.strip().lower() for s in re.split(r"[.!?¡¿]+", text) if len(s.strip().split()) >= 3]


def check_script(script: Script, brief: CreativeBrief, tpl: NarrativeTemplate, language: str,
                 target_s: float, scene_filter: set[int] | None = None) -> list[str]:
    issues: list[str] = []
    if [s.index for s in script.scenes] != [s.index for s in brief.scenes]:
        issues.append("El guion debe tener exactamente las mismas escenas (índices) que el plan creativo")
        return issues
    if not script.hook.strip():
        issues.append("Falta el gancho inicial")
    if not script.closing.strip():
        issues.append("Falta el cierre")
    seen: set[str] = set()
    for scene, plan in zip(script.scenes, brief.scenes):
        if scene_filter is not None and scene.index not in scene_filter:
            continue
        max_words = tpl.max_words(plan.duration_s, language)
        words = len(scene.narration.split())
        if words == 0 and plan.duration_s > 2.5:
            issues.append(f"Escena {scene.index}: falta narración")
        if words > max_words * 1.1:
            issues.append(
                f"Escena {scene.index}: {words} palabras, máximo {max_words} para {plan.duration_s}s "
                f"a velocidad realista; acorta el texto, no aceleres la voz"
            )
        for sent in _sentences(scene.narration):
            if sent in seen:
                issues.append(f"Escena {scene.index}: frase repetida '{sent[:40]}…'")
            seen.add(sent)
    total_speech = sum(tpl.estimate_speech_s(s.narration, language) for s in script.scenes)
    if total_speech > target_s * 1.05:
        issues.append(f"La narración estimada ({total_speech:.1f}s) supera la duración ({target_s}s)")
    if total_speech < target_s * tpl.min_speech_coverage:
        issues.append(f"La narración estimada ({total_speech:.1f}s) es demasiado corta para {target_s}s: "
                      f"amplía el contenido (mínimo {target_s * tpl.min_speech_coverage:.0f}s) para evitar tiempos muertos")
    return issues


def default_subtitle_lines(text: str, max_chars: int = 32) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


TASK = """Eres el guionista de vídeos cortos verticales. Escribe el guion completo siguiendo el plan
creativo (`creative_brief`), escena por escena (mismos índices y secciones).

Requisitos:
- La escena 0 contiene el gancho: frase impactante, pregunta intrigante o promesa narrativa. Nada de
  introducciones lentas ("hola a todos", "en este vídeo...").
- Mantén la atención: información nueva en cada escena, sin redundancias ni frases repetidas.
- Respeta `max_words_per_scene` (velocidad realista de narración con pausas). Es preferible un texto
  más corto y claro que uno que no cabe, pero la narración total debe cubrir al menos el
  `min_speech_coverage` de la duración: nada de tiempos muertos.
- Cierre satisfactorio; llamada a la acción solo si encaja.
- Escribe en el idioma `language`, con ortografía impecable.
- `visual_notes`, `sfx` y `music_cue` por escena; `subtitle_lines` divide la narración en líneas
  cortas (≤ 32 caracteres) legibles en móvil.
- duration_s de cada escena = la del plan creativo.
"""


class ScriptwriterAgent(Agent):
    name = "scriptwriter"
    title = "Guionista"
    phases = frozenset({"script"})
    uses_claude = True

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        spec, tpl = ctx.spec, ctx.narrative
        brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
        previous = ctx.workspace.load("scripts", "script", Script) if ctx.workspace.has("scripts", "script") else None
        context = {
            "creative_brief": brief.model_dump(mode="json"),
            "language": spec.language,
            "topic": spec.topic,
            "idea": spec.idea,
            "narration_type": spec.narration_type,
            "max_words_per_scene": {s.index: tpl.max_words(s.duration_s, spec.language) for s in brief.scenes},
            "min_speech_coverage": tpl.min_speech_coverage,
        }
        scene_filter = ctx.scene_filter
        if previous and scene_filter is not None:
            context["previous_script"] = previous.model_dump(mode="json")
            context["rewrite_only_scenes"] = sorted(scene_filter)
            context["corrections"] = [c.model_dump(mode="json") for c in ctx.corrections if c.target_agent == self.name]
        task = TASK
        if scene_filter is not None:
            task += "\nReescribe SOLO las escenas de `rewrite_only_scenes` aplicando `corrections`; copia el resto sin cambios."

        script = self.ask_llm(
            ctx, phase=phase, task=task, context=context, output_model=Script,
            accept=lambda s: check_script(s, brief, tpl, spec.language, spec.duration_s, scene_filter),
        )
        # Normalización: duraciones del plan y subtítulos por defecto si faltan.
        for scene, plan in zip(script.scenes, brief.scenes):
            scene.duration_s = plan.duration_s
            scene.section = plan.section
            if not scene.subtitle_lines and scene.narration:
                scene.subtitle_lines = default_subtitle_lines(scene.narration)
            if previous and scene_filter is not None and scene.index not in scene_filter:
                prev = next(p for p in previous.scenes if p.index == scene.index)
                scene.narration, scene.subtitle_lines = prev.narration, prev.subtitle_lines
        path = ctx.workspace.save("scripts", "script", script)
        est = sum(tpl.estimate_speech_s(s.narration, spec.language) for s in script.scenes)
        return AgentResult(
            summary=f"Guion '{script.internal_title}': {script.total_words} palabras, ~{est:.0f}s de narración. Gancho: {script.hook[:80]}",
            artifacts={"script": str(path)},
            metrics={"words": script.total_words, "estimated_speech_s": est},
        )
