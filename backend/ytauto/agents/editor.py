"""Agente 6 — Animador / Editor: montaje por escenas, movimiento, transiciones y render."""
from __future__ import annotations

import math
from pathlib import Path

from ..core.models import AssetKind, CreativeBrief, MediaAsset, Script
from ..core.timeline import EditManifest, EditSegment, SoundManifest, VoiceManifest
from ..core.workspace import stable_hash
from ..providers.interfaces import (
    AssembleSpec, EncodeProfile, FinalizeSpec, ProviderCategory, SceneRenderSpec, SubtitleStyle,
)
from .base import Agent, AgentContext, AgentResult

TRANSITION_S = {"low": 0.45, "medium": 0.3, "high": 0.2}
VALID_TRANSITIONS = {"cut", "fade", "slideleft", "slideright", "slideup", "wipeleft", "zoomin", "circleopen"}
VALID_MOTIONS = {"slow_zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "tilt_down", "ken_burns",
                 "punch_in", "drift", "static"}


def shot_changes_for(duration_s: float, max_static_s: float) -> int:
    return max(1, math.ceil(duration_s / max_static_s))


class EditorAgent(Agent):
    name = "editor"
    title = "Animador / Editor"
    phases = frozenset({"edit", "render"})

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        return self._edit(ctx) if phase == "edit" else self._render(ctx)

    # ------------------------------------------------------------------ montaje
    def _edit(self, ctx: AgentContext) -> AgentResult:
        spec = ctx.spec
        brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
        script = ctx.workspace.load("scripts", "script", Script)
        voice = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
        assets = {int(k): MediaAsset.model_validate(v) for k, v in ctx.workspace.load("resources", "assets").items()}
        max_static = ctx.narrative.max_static_shot_s[spec.intensity]
        tr_s = TRANSITION_S[spec.intensity]
        n = len(voice.scenes)
        transitions = []
        for i in range(n - 1):
            t = brief.scenes[i + 1].transition if i + 1 < len(brief.scenes) else "cut"
            transitions.append(t if t in VALID_TRANSITIONS else "fade")

        out_dir = ctx.workspace.dir("scenes")
        segments: list[EditSegment] = []
        rendered = 0
        for k, vs in enumerate(voice.scenes):
            self.progress(ctx, "edit", k / n, f"Escena {vs.index}")
            plan = brief.scenes[vs.index]
            asset = assets[vs.index]
            # Las transiciones con fundido solapan segmentos: se alarga el segmento para compensar.
            overlap = tr_s if k < n - 1 and transitions[k] != "cut" else 0.0
            duration = round(vs.scene_duration_s + overlap, 3)
            motion = plan.camera_motion if plan.camera_motion in VALID_MOTIONS else "slow_zoom_in"
            if motion == "static" and duration > max_static:
                motion = "slow_zoom_in"  # evita planos estáticos largos
            inputs = {
                "asset": asset.sha256 or asset.path, "duration": duration, "motion": motion,
                "shots": shot_changes_for(duration, max_static), "text": plan.on_screen_text,
                "fps": spec.fps,
            }
            h = stable_hash(inputs)
            path = out_dir / f"s{vs.index:02d}_{h}.mp4"
            if not path.exists():
                ctx.providers.invoke(
                    ProviderCategory.RENDERING, "render_scene",
                    SceneRenderSpec(
                        scene_index=vs.index, visual_path=Path(asset.path),
                        visual_kind="video" if asset.kind is AssetKind.VIDEO else "image",
                        duration_s=duration, camera_motion=motion, shot_changes=inputs["shots"],
                        on_screen_text=plan.on_screen_text, fps=spec.fps, out_path=path,
                    ),
                    project_id=ctx.project_id, scene_index=vs.index,
                )
                rendered += 1
            segments.append(EditSegment(index=vs.index, path=str(path), duration_s=duration, input_hash=h,
                                        shots=inputs["shots"]))

        video_path = out_dir / f"master_video_{stable_hash([s.input_hash for s in segments] + transitions)}.mp4"
        if not video_path.exists():
            ctx.providers.invoke(
                ProviderCategory.RENDERING, "assemble",
                AssembleSpec(segments=[Path(s.path) for s in segments], transitions=transitions,
                             transition_s=tr_s, fps=spec.fps, out_path=video_path),
                project_id=ctx.project_id,
            )
        manifest = EditManifest(
            segments=segments, transitions=transitions, transition_s=tr_s, video_path=str(video_path),
            duration_s=voice.total_duration_s, cut_times_s=[s.start_s for s in voice.scenes[1:]],
        )
        path = ctx.workspace.save("scenes", "edit_manifest", manifest)
        self.progress(ctx, "edit", 1.0)
        return AgentResult(
            summary=f"Montaje: {n} escenas ({rendered} renderizadas, {n - rendered} reutilizadas), {manifest.duration_s:.1f}s",
            artifacts={"edit_manifest": str(path), "video": str(video_path)},
            metrics={"rendered": rendered, "reused": n - rendered},
        )

    # ------------------------------------------------------------------ render final
    def _render(self, ctx: AgentContext) -> AgentResult:
        edit = ctx.workspace.load("scenes", "edit_manifest", EditManifest)
        sound = ctx.workspace.load("sound", "sound_manifest", SoundManifest)
        voice = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
        script = ctx.workspace.load("scripts", "script", Script)
        profile = EncodeProfile(fps=ctx.spec.fps)
        meta = {"title": script.internal_title, "comment": f"ytauto project {ctx.project_id}"}
        clean = ctx.workspace.dir("exports") / "master_clean.mp4"
        preview = ctx.workspace.dir("review") / "master_preview.mp4"
        preview_style = SubtitleStyle(mode=ctx.spec.subtitle_mode or "karaoke")
        for out, style, draft in ((clean, None, False), (preview, preview_style, True)):
            ctx.providers.invoke(
                ProviderCategory.RENDERING, "finalize",
                FinalizeSpec(video_path=Path(edit.video_path), audio_path=Path(sound.mix_path),
                             subtitles=voice.cues if style else [], subtitle_style=style,
                             profile=profile, metadata=meta, draft=draft, out_path=out),
                project_id=ctx.project_id,
            )
        return AgentResult(
            summary="Render final: máster limpio + previsualización con subtítulos",
            artifacts={"master_clean": str(clean), "master_preview": str(preview)},
        )
