"""Agente 7 — Sonido: música, efectos, mezcla, ducking y normalización."""
from __future__ import annotations

from pathlib import Path

from ..core.errors import ProviderError, ProviderNotConfigured
from ..core.models import CreativeBrief, Script, Section
from ..core.timeline import EditManifest, SoundManifest, VoiceManifest
from ..providers.interfaces import (
    AudioMixSpec,
    AudioTrack,
    MusicRequest,
    ProviderCategory,
    SFXRequest,
)
from .base import Agent, AgentContext, AgentResult

MUSIC_GAIN_DB = -14.0  # bajo la voz; el ducking baja más cuando hay narración
SFX_GAIN_DB = -9.0
TRANSITION_SFX = {"fade": "whoosh", "slideleft": "whoosh", "slideright": "whoosh", "slideup": "whoosh",
                  "wipeleft": "whoosh", "zoomin": "riser", "circleopen": "pop"}


class SoundAgent(Agent):
    name = "sound"
    title = "Sonido"
    phases = frozenset({"sound"})

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        brief = ctx.workspace.load("planning", "creative_brief", CreativeBrief)
        script = ctx.workspace.load("scripts", "script", Script)
        voice = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
        edit = ctx.workspace.load("scenes", "edit_manifest", EditManifest)
        out_dir = ctx.workspace.dir("sound")
        total = voice.total_duration_s
        tracks: list[AudioTrack] = []

        for vs in voice.scenes:
            if vs.path:
                tracks.append(AudioTrack(path=Path(vs.path), start_s=vs.start_s + vs.voice_offset_s, role="voice"))

        music_id = None
        music_provider = music_credit = None
        if (ctx.spec.music or "").lower() not in ("none", "sin música", "no"):
            self.progress(ctx, phase, 0.2, "Música")
            mood = ctx.spec.music or brief.music_direction or script.music
            try:
                music = ctx.providers.invoke(
                    ProviderCategory.MUSIC, "get_track",
                    MusicRequest(mood=mood, duration_s=total, out_dir=out_dir), project_id=ctx.project_id,
                )
                music_id = music.id
                music_provider = music.provider
                if music.metadata.get("attribution_required") and music.license.attribution:
                    music_credit = music.license.attribution
                tracks.append(AudioTrack(path=Path(music.path), role="music", gain_db=MUSIC_GAIN_DB,
                                         loop=(music.duration_s or 0) < total, fade_in_s=0.5, fade_out_s=1.5))
            except (ProviderNotConfigured, ProviderError) as e:
                ctx.memory.add_decision(self.name, f"Sin música: {e}")

        self.progress(ctx, phase, 0.5, "Efectos")
        sfx_plan: list[tuple[str, float]] = []
        narrative: set[str] = set()  # efectos descritos en el guion (los puede generar la IA si lo elegiste)
        ai_sfx = "sfx" in ctx.spec.audio_features
        for t, cut in zip(edit.transitions, edit.cut_times_s):
            if t in TRANSITION_SFX:
                sfx_plan.append((TRANSITION_SFX[t], max(0.0, cut - edit.transition_s)))
        for vs in voice.scenes:
            sc = script.scenes[vs.index]
            if sc.section is Section.CLIMAX and vs.index > 0 and script.scenes[vs.index - 1].section is not Section.CLIMAX:
                sfx_plan.append(("impact", vs.start_s))
            for effect in sc.sfx[:1]:  # un efecto pedido por escena como máximo, para no saturar
                sfx_plan.append((effect, vs.start_s + 0.1))
                if ai_sfx and len(effect.split()) >= 2:
                    narrative.add(effect)
        if voice.scenes and voice.scenes[0].path:
            sfx_plan.append(("impact", 0.0))  # golpe de arranque del gancho

        sfx_log = []
        cache: dict[str, str] = {}
        for effect, at in sfx_plan:
            try:
                if effect not in cache:
                    asset = ctx.providers.invoke(ProviderCategory.SFX, "get_effect",
                                                 SFXRequest(effect=effect, out_dir=out_dir,
                                                            descriptive=effect in narrative),
                                                 project_id=ctx.project_id)
                    cache[effect] = asset.path
                tracks.append(AudioTrack(path=Path(cache[effect]), start_s=round(at, 3), role="sfx", gain_db=SFX_GAIN_DB))
                sfx_log.append({"effect": effect, "at_s": round(at, 3)})
            except (ProviderNotConfigured, ProviderError):
                continue

        self.progress(ctx, phase, 0.8, "Mezcla")
        mix_path = out_dir / "mix.wav"
        ctx.providers.invoke(
            ProviderCategory.RENDERING, "mix_audio",
            AudioMixSpec(tracks=tracks, duration_s=total, duck_music_under_voice=True, out_path=mix_path),
            project_id=ctx.project_id,
        )
        manifest = SoundManifest(mix_path=str(mix_path), music_asset_id=music_id, music_provider=music_provider,
                                 music_credit=music_credit, sfx=sfx_log, duration_s=total)
        path = ctx.workspace.save("sound", "sound_manifest", manifest)
        return AgentResult(
            summary=f"Mezcla: voz + {'música' if music_id else 'sin música'} + {len(sfx_log)} efectos, −14 LUFS",
            artifacts={"sound_manifest": str(path), "mix": str(mix_path)},
            metrics={"sfx": len(sfx_log)},
        )
