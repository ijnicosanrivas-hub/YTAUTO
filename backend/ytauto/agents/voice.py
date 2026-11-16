"""Agente 5 — Voz: locución por escena, ritmo, pronunciación y sincronización."""
from __future__ import annotations

import re

from pydantic import BaseModel

from ..core.models import MAX_DURATION_S, MIN_DURATION_S, CorrectionRequest, Script
from ..core.timeline import VoiceManifest, VoiceScene
from ..core.workspace import stable_hash
from ..providers.interfaces import ProviderCategory, SubtitleRequest, TTSRequest, Voice
from .base import Agent, AgentContext, AgentResult

SPEED_BY_INTENSITY = {"low": 0.95, "medium": 1.0, "high": 1.05}
MAX_SPEED = 1.1
OVERRUN_TOLERANCE = 1.15
TAIL_PAD_S = 0.35

_REPLACEMENTS = {
    "es": [(r"%", " por ciento"), (r"&", " y "), (r"\bvs\.?\b", "contra"), (r"\bkm\b", "kilómetros")],
    "en": [(r"%", " percent"), (r"&", " and "), (r"\bvs\.?\b", "versus")],
}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿]")


def normalize_for_tts(text: str, language: str) -> str:
    text = _EMOJI.sub("", text)
    for pattern, repl in _REPLACEMENTS.get(language, []):
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


class Pronunciations(BaseModel):
    scenes: dict[int, str]  # índice -> texto preparado para TTS


def choose_voice(voices: list[Voice], language: str, voice_type: str | None) -> Voice | None:
    candidates = [v for v in voices if v.language.split("-")[0] == language.split("-")[0]] or voices
    if voice_type:
        wanted = voice_type.lower()
        for v in candidates:
            if wanted in f"{v.name} {v.gender or ''} {v.style or ''}".lower():
                return v
    return candidates[0] if candidates else None


class VoiceAgent(Agent):
    name = "voice"
    title = "Voz"
    phases = frozenset({"voice"})
    uses_claude = True  # solo si se activa la revisión de pronunciación con Claude

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        spec = ctx.spec
        script = ctx.workspace.load("scripts", "script", Script)
        previous = (ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
                    if ctx.workspace.has("voice", "voice_manifest") else None)
        prev_by_idx = {s.index: s for s in previous.scenes} if previous else {}

        voices = ctx.providers.query(ProviderCategory.TTS, "list_voices", spec.language)
        voice = choose_voice(voices, spec.language, spec.voice_type)
        speed = SPEED_BY_INTENSITY[spec.intensity]
        texts = {s.index: normalize_for_tts(s.narration, spec.language) for s in script.scenes}
        if ctx.settings.get("voice_llm_pronunciation"):
            texts = self._llm_pronunciation(ctx, texts)

        out_dir = ctx.workspace.dir("voice")
        scenes: list[VoiceScene] = []
        corrections: list[CorrectionRequest] = []
        for n, sc in enumerate(script.scenes):
            self.progress(ctx, phase, n / len(script.scenes), f"Escena {sc.index}")
            text = texts[sc.index]
            th = stable_hash([text, voice.id if voice else None, speed])
            prev = prev_by_idx.get(sc.index)
            if prev and prev.text_hash == th and not (ctx.scene_filter and sc.index in ctx.scene_filter):
                voice_scene = prev.model_copy(update={"scene_duration_s": sc.duration_s})
                voice_scene.scene_duration_s = max(sc.duration_s, voice_scene.voice_duration_s + voice_scene.voice_offset_s + TAIL_PAD_S)
                scenes.append(voice_scene)
                continue
            if not text:
                scenes.append(VoiceScene(index=sc.index, path=None, scene_duration_s=sc.duration_s, text_hash=th))
                continue
            path = out_dir / f"s{sc.index:02d}_{th}.wav"
            asset = self._synth(ctx, text, voice, speed, path, sc.index)
            dur = asset.duration_s or 0.0
            if dur > sc.duration_s * OVERRUN_TOLERANCE and speed < MAX_SPEED:
                asset = self._synth(ctx, text, voice, MAX_SPEED, path, sc.index)
                dur = asset.duration_s or 0.0
            if dur > sc.duration_s * OVERRUN_TOLERANCE:
                corrections.append(CorrectionRequest(
                    target_agent="scriptwriter", phase="script", scene_index=sc.index,
                    reason=f"La locución dura {dur:.1f}s y la escena {sc.duration_s:.1f}s: acorta la narración",
                ))
            offset = 0.15
            scenes.append(VoiceScene(
                index=sc.index, path=str(path), voice_duration_s=round(dur, 3), voice_offset_s=offset,
                scene_duration_s=round(max(sc.duration_s, dur + offset + TAIL_PAD_S), 3), text_hash=th,
            ))

        manifest = VoiceManifest(voice_id=voice.id if voice else None, speed=speed, scenes=scenes)
        self._fit_total(manifest, spec.duration_s, corrections)
        manifest.recompute_starts()
        manifest.cues = self._align(ctx, script, manifest, texts)
        path = ctx.workspace.save("voice", "voice_manifest", manifest)
        self.progress(ctx, phase, 1.0)
        return AgentResult(
            status="in_review" if corrections else "completed",
            summary=f"Locución con voz '{manifest.voice_id}', {manifest.total_duration_s:.1f}s totales, "
                    f"{len(manifest.cues)} subtítulos",
            artifacts={"voice_manifest": str(path)},
            corrections=corrections,
            metrics={"total_duration_s": manifest.total_duration_s},
        )

    # ------------------------------------------------------------------ auxiliares
    def _synth(self, ctx, text, voice, speed, path, scene_index):
        return ctx.providers.invoke(
            ProviderCategory.TTS, "synthesize",
            TTSRequest(text=text, language=ctx.spec.language, voice_id=voice.id if voice else None,
                       speed=speed, out_path=path),
            project_id=ctx.project_id, scene_index=scene_index,
        )

    @staticmethod
    def _fit_total(manifest: VoiceManifest, target_s: float, corrections: list[CorrectionRequest]) -> None:
        total = manifest.total_duration_s
        if total < max(MIN_DURATION_S, target_s - 1.5):
            # Faltan segundos: se reparten entre escenas (más tiempo de imagen, no de voz).
            goal = max(MIN_DURATION_S, target_s)
            extra = (goal - total) / len(manifest.scenes)
            for s in manifest.scenes:
                s.scene_duration_s = round(s.scene_duration_s + extra, 3)
        elif total > MAX_DURATION_S:
            longest = sorted(manifest.scenes, key=lambda s: s.voice_duration_s, reverse=True)[:2]
            for s in longest:
                if not any(c.scene_index == s.index for c in corrections):
                    corrections.append(CorrectionRequest(
                        target_agent="scriptwriter", phase="script", scene_index=s.index,
                        reason=f"Duración total {total:.1f}s supera {MAX_DURATION_S}s; acorta esta escena",
                    ))

    def _align(self, ctx, script: Script, manifest: VoiceManifest, texts: dict[int, str]):
        cues = []
        by_idx = {s.index: s for s in script.scenes}
        for vs in manifest.scenes:
            if not vs.path:
                continue
            cues += ctx.providers.query(
                ProviderCategory.SUBTITLE, "align",
                SubtitleRequest(text=by_idx[vs.index].narration, audio_path=vs.path,
                                audio_duration_s=vs.voice_duration_s, language=ctx.spec.language,
                                offset_s=vs.start_s + vs.voice_offset_s),
            )
        return cues

    def _llm_pronunciation(self, ctx: AgentContext, texts: dict[int, str]) -> dict[int, str]:
        result = self.ask_llm(
            ctx, phase="voice",
            task=("Prepara cada narración para un motor de síntesis de voz: escribe números, siglas, "
                  "símbolos y nombres extranjeros tal como deben pronunciarse en el idioma indicado, "
                  "y añade comas donde convenga una pausa natural. No cambies el contenido."),
            context={"language": ctx.spec.language, "scenes": texts},
            output_model=Pronunciations,
            accept=lambda p: [] if set(p.scenes) == set(texts) else ["Debe devolver todas las escenas"],
        )
        return result.scenes
