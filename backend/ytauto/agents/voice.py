"""Agente 5 — Voz: locución por escena, ritmo, pronunciación y sincronización."""
from __future__ import annotations

import math
import re

from pydantic import BaseModel

from ..core.audio_features import AUDIO_TAGS, parse_dialogue, role_voice, same_words, strip_tags
from ..core.captions import regroup_cues
from ..core.models import MAX_DURATION_S, MIN_DURATION_S, CorrectionRequest, Script
from ..core.timeline import VoiceManifest, VoiceScene
from ..core.workspace import stable_hash
from ..providers.interfaces import (DialogueLine, ProviderCategory, SubtitleCue, SubtitleRequest, TTSRequest, Voice,
                                    WordTiming)
from .base import Agent, AgentContext, AgentResult

SPEED_BY_INTENSITY = {"low": 0.95, "medium": 1.0, "high": 1.05}
MAX_SPEED = 1.1
OVERRUN_TOLERANCE = 1.15
TAIL_PAD_S = 0.35
MAX_SCENE_GAP_S = 0.8  # silencio máximo tolerado tras la voz dentro de una escena
MIN_SCENE_S = 1.5
VOICE_OFFSET_S = 0.15  # la voz empieza justo después del corte (gancho inmediato)
DURATION_SAFETY_S = 0.3  # margen sobre el mínimo: la codificación redondea a fotogramas enteros
LENGTHEN_THRESHOLD_S = 3.0  # déficits menores se resuelven ajustando escenas, sin gastar rondas


def fit_scene(planned_s: float, voice_s: float, offset_s: float = VOICE_OFFSET_S) -> float:
    """Duración de escena ajustada a la locución: sin cortar la voz y sin tiempos muertos."""
    tight = voice_s + offset_s + TAIL_PAD_S
    if tight >= planned_s:
        return round(tight, 3)
    return round(max(MIN_SCENE_S, min(planned_s, tight + MAX_SCENE_GAP_S)), 3)

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


PERFORMANCE_TASK = """Eres director de doblaje de vídeos cortos virales. Marca cómo debe INTERPRETARSE cada narración
para Eleven v4, sin cambiar ni una palabra del texto:
- Añade etiquetas de interpretación entre corchetes delante de la frase o fragmento al que afectan, elegidas de
  `allowed_tags` o descripciones claras de la voz en inglés (p. ej. [low, gravelly voice]). Nada de etiquetas de
  efectos de sonido (eso lo hace el agente de sonido).
- Interpreta según la intención narrativa: susurro en la tensión, voz temblorosa en el miedo, sorpresa o
  incredulidad en el giro, intensidad creciente hacia el clímax y una pausa («…») justo antes de revelar algo.
- Usa también puntos suspensivos para pausas y MAYÚSCULAS para el énfasis de una palabra clave (con moderación).
- No uses SSML (<break>): Eleven v4 no lo admite. Varía: no repitas la misma etiqueta en todas las escenas.
- Devuelve todas las escenas; las palabras deben ser EXACTAMENTE las mismas que en `scenes`."""


class Performance(BaseModel):
    scenes: dict[int, str]  # índice -> narración con etiquetas de interpretación


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

        voices = ctx.providers.query(ProviderCategory.TTS, "list_voices", spec.language, project_id=ctx.project_id)
        voice = choose_voice(voices, spec.language, spec.voice_type)
        speed = SPEED_BY_INTENSITY[spec.intensity]
        texts = {s.index: normalize_for_tts(s.narration, spec.language) for s in script.scenes}
        if ctx.settings.get("voice_llm_pronunciation"):
            texts = self._llm_pronunciation(ctx, texts)
        features = set(spec.audio_features)
        cast = {k: v for k, v in spec.voice_cast.items() if v}
        if cast.get("narrador") and any(v.id == cast["narrador"] for v in voices):
            voice = next(v for v in voices if v.id == cast["narrador"])  # la voz del canal
        performance = self._performance(ctx, texts) if "expressive" in features else {}
        dialogues = {s.index: parse_dialogue(s.dialogue) for s in script.scenes} if "dialogue" in features and cast else {}
        references = self._references(ctx) if "voice_changer" in features else {}

        out_dir = ctx.workspace.dir("voice")
        scenes: list[VoiceScene] = []
        corrections: list[CorrectionRequest] = []
        for n, sc in enumerate(script.scenes):
            self.progress(ctx, phase, n / len(script.scenes), f"Escena {sc.index}")
            lines = dialogues.get(sc.index) or []
            text = " ".join([texts[sc.index], *(t for _, t in lines)]).strip()
            th = stable_hash([text, voice.id if voice else None, speed, performance.get(sc.index), lines,
                              str(references.get(sc.index) or ""), sorted(features), cast])
            prev = prev_by_idx.get(sc.index)
            if prev and prev.text_hash == th and not (ctx.scene_filter and sc.index in ctx.scene_filter):
                voice_scene = prev.model_copy(update={
                    "planned_duration_s": sc.duration_s,
                    "scene_duration_s": fit_scene(sc.duration_s, prev.voice_duration_s, prev.voice_offset_s)})
                scenes.append(voice_scene)
                continue
            if not text:
                scenes.append(VoiceScene(index=sc.index, path=None, scene_duration_s=sc.duration_s,
                                         planned_duration_s=sc.duration_s, text_hash=th))
                continue
            path = out_dir / f"s{sc.index:02d}_{th}.wav"
            extra = self._extras(texts[sc.index], performance.get(sc.index), lines, cast, voice,
                                 references.get(sc.index), "word_timing" in features)
            asset = self._synth(ctx, text, voice, speed, path, sc.index, **extra)
            dur = asset.duration_s or 0.0
            if dur > sc.duration_s * OVERRUN_TOLERANCE and speed < MAX_SPEED and not extra:
                asset = self._synth(ctx, text, voice, MAX_SPEED, path, sc.index)
                dur = asset.duration_s or 0.0
            if dur > sc.duration_s * OVERRUN_TOLERANCE:
                corrections.append(CorrectionRequest(
                    target_agent="scriptwriter", phase="script", scene_index=sc.index,
                    reason=f"La locución dura {dur:.1f}s y la escena {sc.duration_s:.1f}s: acorta la narración",
                ))
            scenes.append(VoiceScene(
                index=sc.index, path=str(path), voice_duration_s=round(dur, 3), voice_offset_s=VOICE_OFFSET_S,
                scene_duration_s=fit_scene(sc.duration_s, dur), planned_duration_s=sc.duration_s, text_hash=th,
                word_timings=list(asset.metadata.get("word_timings") or []), spoken_text=text,
            ))

        manifest = VoiceManifest(voice_id=voice.id if voice else None, speed=speed, scenes=scenes)
        can_request = ctx.settings.get("correction_rounds", 0) < ctx.settings.get("max_correction_rounds", 2)
        note = self._fit_total(manifest, spec.duration_s, corrections, can_request)
        if note:
            ctx.memory.add_decision(self.name, note)
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
    def _synth(self, ctx, text, voice, speed, path, scene_index, **extra):
        return ctx.providers.invoke(
            ProviderCategory.TTS, "synthesize",
            TTSRequest(text=text, language=ctx.spec.language, voice_id=voice.id if voice else None,
                       speed=speed, out_path=path, **extra),
            project_id=ctx.project_id, scene_index=scene_index,
        )

    @staticmethod
    def _extras(narration: str, performed: str | None, lines: list[tuple[str, str]], cast: dict[str, str],
                voice: Voice | None, reference, timings: bool) -> dict:
        """Opciones para motores avanzados (los demás leen el texto plano y las ignoran)."""
        extra: dict = {}
        if reference:
            extra["reference_audio"] = reference
        elif lines:
            narrator = cast.get("narrador") or (voice.id if voice else None)
            dialogue = [DialogueLine(voice_id=narrator, text=performed or narration, role="narrador")] \
                if narrator and narration else []
            for role, line in lines:
                vid = role_voice(role, cast)
                if vid:
                    dialogue.append(DialogueLine(voice_id=vid, text=line, role=role))
            if len({d.voice_id for d in dialogue}) > 1:
                extra["dialogue"] = dialogue
        if performed and "dialogue" not in extra and "reference_audio" not in extra:
            extra["performance_text"] = performed
        if timings:
            extra["want_word_timings"] = True
        return extra

    def _performance(self, ctx: AgentContext, texts: dict[int, str]) -> dict[int, str]:
        """Interpretación emocional (etiquetas de Eleven v4). Si Claude falla, se narra sin etiquetas."""
        wanted = {i: t for i, t in texts.items() if t}
        if not wanted:
            return {}
        try:
            result = self.ask_llm(
                ctx, phase="voice", task=PERFORMANCE_TASK, output_model=Performance,
                context={"language": ctx.spec.language, "scenes": wanted, "allowed_tags": AUDIO_TAGS,
                         "intensity": ctx.spec.intensity},
                accept=lambda p: [f"Escena {i}: cambia las palabras del texto (solo puedes añadir etiquetas, «…» o "
                                  f"MAYÚSCULAS)" for i, t in wanted.items() if not same_words(t, p.scenes.get(i, ""))],
            )
        except Exception as e:  # noqa: BLE001 - la interpretación es una mejora: nunca bloquea la locución
            ctx.memory.add_decision(self.name, f"Sin interpretación emocional ({type(e).__name__}): narración neutra")
            return {}
        out = {i: result.scenes[i] for i in wanted if result.scenes.get(i) and result.scenes[i] != wanted[i]}
        ctx.workspace.save("voice", "performance", {str(k): v for k, v in out.items()})
        return out

    @staticmethod
    def _references(ctx: AgentContext) -> dict[int, object]:
        """Grabaciones del usuario por escena (voice/reference_<n>.*) para el Voice Changer."""
        folder = ctx.workspace.dir("voice")
        out = {}
        for f in folder.glob("reference_*"):
            try:
                out[int(f.stem.split("_", 1)[1])] = f
            except ValueError:
                continue
        return out

    @staticmethod
    def _fit_total(manifest: VoiceManifest, target_s: float, corrections: list[CorrectionRequest],
                   can_request: bool = True) -> str | None:
        """Ajusta la duración total. Devuelve una nota para la memoria si se tomó una decisión."""
        total = manifest.total_duration_s
        lower = max(MIN_DURATION_S + DURATION_SAFETY_S, target_s * 0.85)
        if total < lower:
            deficit = lower - total
            if can_request and deficit > LENGTHEN_THRESHOLD_S:
                # Narración insuficiente: se pide al guionista ampliar las escenas con más hueco.
                gaps = sorted(manifest.scenes, key=lambda s: s.planned_duration_s - s.voice_duration_s, reverse=True)
                for s in gaps[:3]:
                    if s.planned_duration_s - s.voice_duration_s > 0.5:
                        corrections.append(CorrectionRequest(
                            target_agent="scriptwriter", phase="script", scene_index=s.index, severity="minor",
                            reason=(f"La locución ({total:.1f}s en total) no llena el vídeo de {target_s}s: amplía "
                                    f"la narración de esta escena (≈{s.planned_duration_s - s.voice_duration_s:.1f}s libres)"),
                        ))
                if corrections:
                    return None
            # Último recurso: se reparte el tiempo que falta (más imagen, no más silencio largo).
            goal = lower
            extra = math.ceil((goal - total) / len(manifest.scenes) * 1000) / 1000  # redondeo hacia arriba
            for s in manifest.scenes:
                s.scene_duration_s = round(s.scene_duration_s + extra, 3)
            return (f"Narración corta ({total:.1f}s): se alargan las escenas {extra:.2f}s cada una hasta "
                    f"{goal:.1f}s (deficit {deficit:.1f}s)")
        if total > MAX_DURATION_S:
            longest = sorted(manifest.scenes, key=lambda s: s.voice_duration_s, reverse=True)[:2]
            for s in longest:
                if not any(c.scene_index == s.index for c in corrections):
                    corrections.append(CorrectionRequest(
                        target_agent="scriptwriter", phase="script", scene_index=s.index,
                        reason=f"Duración total {total:.1f}s supera {MAX_DURATION_S}s; acorta esta escena",
                    ))
        return None

    def _align(self, ctx, script: Script, manifest: VoiceManifest, texts: dict[int, str]):
        cues = []
        by_idx = {s.index: s for s in script.scenes}
        for vs in manifest.scenes:
            if not vs.path:
                continue
            if vs.word_timings:
                # Tiempos exactos devueltos con el audio: cada palabra se resalta justo cuando se pronuncia.
                cues += cues_from_timings(vs.word_timings, vs.start_s + vs.voice_offset_s,
                                          by_idx[vs.index].subtitle_lines)
                continue
            scene_cues = ctx.providers.query(
                ProviderCategory.SUBTITLE, "align",
                SubtitleRequest(text=strip_tags(vs.spoken_text) or by_idx[vs.index].narration, audio_path=vs.path,
                                audio_duration_s=vs.voice_duration_s, language=ctx.spec.language,
                                offset_s=vs.start_s + vs.voice_offset_s), project_id=ctx.project_id)
            # Los cortes de línea que escribió el guionista (pensados para leer en móvil) tienen prioridad.
            cues += regroup_cues(scene_cues, by_idx[vs.index].subtitle_lines)
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


def cues_from_timings(timings: list[dict], offset_s: float, lines: list[str], max_chars: int = 32) -> list[SubtitleCue]:
    """Subtítulos a partir de los tiempos por palabra: respeta los cortes del guionista si coinciden."""
    words = [WordTiming(word=str(w["word"]), start_s=round(float(w["start_s"]) + offset_s, 3),
                        end_s=round(max(float(w["end_s"]), float(w["start_s"]) + 0.05) + offset_s, 3)) for w in timings]
    if not words:
        return []
    whole = [SubtitleCue(start_s=words[0].start_s, end_s=words[-1].end_s, text=" ".join(w.word for w in words),
                         words=words)]
    regrouped = regroup_cues(whole, lines)
    if regrouped is not whole:
        return regrouped
    out, chunk = [], []
    for w in words:
        if chunk and len(" ".join(x.word for x in [*chunk, w])) > max_chars:
            out.append(SubtitleCue(start_s=chunk[0].start_s, end_s=chunk[-1].end_s,
                                   text=" ".join(x.word for x in chunk), words=chunk))
            chunk = []
        chunk.append(w)
    if chunk:
        out.append(SubtitleCue(start_s=chunk[0].start_s, end_s=chunk[-1].end_s, text=" ".join(x.word for x in chunk),
                               words=chunk))
    return out
