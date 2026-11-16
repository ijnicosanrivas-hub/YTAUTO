"""Agente 4 — Recursos visuales (prompts, búsqueda/generación, procedencia y licencias)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.errors import ProviderError, ProviderNotConfigured
from ..core.workspace import stable_hash
from ..core.models import CreativeBrief, MediaAsset, ScenePrompt, Script
from ..providers.interfaces import ImageRequest, ProviderCategory, VideoRequest
from .base import Agent, AgentContext, AgentResult

MIN_SHORT_SIDE = 540  # por debajo, el recorte a 1080×1920 pierde demasiada calidad


class ScenePrompts(BaseModel):
    style_guide: str = Field(description="Guía estética común para mantener coherencia visual")
    prompts: list[ScenePrompt]


def check_prompts(p: ScenePrompts, scene_indices: list[int]) -> list[str]:
    issues = []
    got = sorted(x.scene_index for x in p.prompts)
    if got != sorted(scene_indices):
        issues.append(f"Debe haber un prompt por escena {scene_indices} (recibido {got})")
    queries = [x.search_query.strip().lower() for x in p.prompts]
    if len(set(queries)) < len(queries):
        issues.append("Las búsquedas (search_query) deben ser distintas para evitar imágenes repetitivas")
    for x in p.prompts:
        if len(x.prompt.split()) < 5:
            issues.append(f"Escena {x.scene_index}: prompt demasiado pobre")
    return issues


def check_asset(asset: MediaAsset) -> list[str]:
    issues = []
    if asset.width and asset.height:
        if min(asset.width, asset.height) < MIN_SHORT_SIDE:
            issues.append(f"Resolución insuficiente {asset.width}x{asset.height}")
    if not asset.license or asset.license.name == "unknown":
        issues.append("Licencia/procedencia no registrada")
    return issues


TASK = """Eres el responsable de recursos visuales de vídeos cortos verticales 9:16. Para cada escena
del guion, crea:
- `prompt`: descripción detallada para un generador de imágenes/clips (composición vertical,
  sujeto, luz, encuadre, estilo), coherente con `visual_style` y la paleta.
- `search_query`: 2-5 palabras en inglés para buscar en bancos de imágenes/vídeo.
- `kind`: "video" si la escena gana mucho con movimiento real; si no, "image".
- `style_tags`: etiquetas de estilo comunes a todo el vídeo.
Evita imágenes repetitivas: cada escena debe aportar algo visualmente distinto.
"""


class ResourcesAgent(Agent):
    name = "resources"
    title = "Recursos"
    phases = frozenset({"scene_prep", "resource_generation"})
    uses_claude = True

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        return self._prep(ctx) if phase == "scene_prep" else self._generate(ctx)

    # ------------------------------------------------------------------ fase 6
    def _prep(self, ctx: AgentContext) -> AgentResult:
        brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
        script = ctx.workspace.load("scripts", "script", Script)
        indices = [s.index for s in script.scenes]
        context = {
            "visual_style": brief.visual_style,
            "palette": brief.palette,
            "tone": brief.tone,
            "scenes": [
                {"index": s.index, "section": s.section.value, "narration": s.narration,
                 "visual_notes": s.visual_notes,
                 "visual_direction": brief.scenes[s.index].visual_direction}
                for s in script.scenes
            ],
        }
        result = self.ask_llm(
            ctx, phase="scene_prep", task=TASK, context=context, output_model=ScenePrompts,
            accept=lambda p: check_prompts(p, indices),
        )
        result.prompts.sort(key=lambda p: p.scene_index)
        if ctx.scene_filter is not None and ctx.workspace.has("resources", "prompts"):
            # Corrección parcial: se conservan los prompts de las escenas no afectadas.
            prev = {p.scene_index: p for p in ctx.workspace.load("resources", "prompts", ScenePrompts).prompts}
            result.prompts = [p if p.scene_index in ctx.scene_filter else prev.get(p.scene_index, p)
                              for p in result.prompts]
            result.style_guide = ctx.workspace.load("resources", "prompts", ScenePrompts).style_guide
        path = ctx.workspace.save("resources", "prompts", result)
        return AgentResult(summary=f"{len(result.prompts)} prompts visuales. Guía: {result.style_guide[:100]}",
                           artifacts={"prompts": str(path)})

    # ------------------------------------------------------------------ fase 7
    def _generate(self, ctx: AgentContext) -> AgentResult:
        prompts = ctx.workspace.load("resources", "prompts", ScenePrompts)
        brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
        existing: dict[str, dict] = (
            ctx.workspace.load("resources", "assets") if ctx.workspace.has("resources", "assets") else {}
        )
        out_dir = ctx.workspace.dir("resources")
        used_hashes = [a.get("perceptual_hash") for a in existing.values() if a.get("perceptual_hash")]
        warnings: list[str] = []
        def stale(p: ScenePrompt) -> bool:
            prev = existing.get(str(p.scene_index))
            return prev is None or prev.get("metadata", {}).get("prompt_hash") != stable_hash(p.model_dump(mode="json"))

        forced = ctx.scene_filter or set()
        todo = [p for p in prompts.prompts if p.scene_index in forced or stale(p)]
        for n, p in enumerate(todo):
            self.progress(ctx, "resource_generation", n / max(1, len(todo)), f"Escena {p.scene_index}")
            prev = existing.get(str(p.scene_index))
            exclude = list(used_hashes)
            if prev and prev.get("perceptual_hash"):
                exclude.append(prev["perceptual_hash"])  # si se rehace, que sea distinta
            style = list(dict.fromkeys([*p.style_tags, brief.visual_style]))
            asset = self._fetch(ctx, p, style, exclude, out_dir, brief.scenes[p.scene_index].duration_s)
            asset.project_id, asset.scene_index = ctx.project_id, p.scene_index
            asset.metadata["prompt_hash"] = stable_hash(p.model_dump(mode="json"))
            for issue in check_asset(asset):
                warnings.append(f"Escena {p.scene_index}: {issue}")
            if asset.perceptual_hash:
                used_hashes.append(asset.perceptual_hash)
            existing[str(p.scene_index)] = asset.model_dump(mode="json")
            ctx.workspace.save("resources", "assets", existing)  # persistencia por escena
        self.progress(ctx, "resource_generation", 1.0)
        path = ctx.workspace.save("resources", "assets", existing)
        return AgentResult(
            summary=f"{len(todo)} recursos preparados ({len(existing)} escenas cubiertas)"
                    + (f"; avisos: {len(warnings)}" if warnings else ""),
            artifacts={"assets": str(path)},
            metrics={"generated": len(todo), "warnings": warnings},
        )

    def _fetch(self, ctx: AgentContext, p: ScenePrompt, style: list[str], exclude: list[str],
               out_dir, duration_s: float) -> MediaAsset:
        if p.kind == "video":
            try:
                return ctx.providers.invoke(
                    ProviderCategory.VIDEO, "generate",
                    VideoRequest(prompt=p.prompt, search_query=p.search_query, duration_s=duration_s,
                                 exclude_hashes=exclude, out_dir=out_dir),
                    project_id=ctx.project_id, scene_index=p.scene_index,
                )
            except (ProviderNotConfigured, ProviderError) as e:
                ctx.memory.add_decision(self.name, f"Escena {p.scene_index}: sin clip de vídeo ({e}); uso imagen")
        return ctx.providers.invoke(
            ProviderCategory.IMAGE, "generate",
            ImageRequest(prompt=p.prompt, search_query=p.search_query, negative_prompt=p.negative_prompt,
                         style_tags=style, exclude_hashes=exclude, seed=p.scene_index, out_dir=out_dir),
            project_id=ctx.project_id, scene_index=p.scene_index,
        )
