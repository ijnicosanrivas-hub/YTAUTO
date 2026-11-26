"""Agente 8 — Revisor independiente con puntuación interna 0-100.

La puntuación mide calidad técnica y editorial según criterios explícitos. NO es una
predicción de viralidad ni de rendimiento en plataformas.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..core.models import MAX_DURATION_S, MIN_DURATION_S, CorrectionRequest, Script
from ..core.timeline import EditManifest, VoiceManifest
from ..providers.interfaces import ProviderCategory
from .base import Agent, AgentContext, AgentResult

DEFAULT_THRESHOLD = 75
EXPECTED_W, EXPECTED_H = 1080, 1920


class EditorialScores(BaseModel):
    hook: int = Field(ge=0, le=10, description="Fuerza del gancho en los primeros 3 s")
    pacing: int = Field(ge=0, le=10, description="Ritmo, sin pausas ni redundancias")
    coherence: int = Field(ge=0, le=10, description="Coherencia narrativa y cierre")
    spelling: int = Field(ge=0, le=10, description="Ortografía y gramática")
    legibility: int = Field(ge=0, le=10, description="Subtítulos cortos y legibles")
    payoff: int = Field(default=7, ge=0, le=10, description="El vídeo cumple lo que promete el gancho (recompensa)")


TargetAgent = Literal["director", "scriptwriter", "resources", "voice", "editor", "sound"]
# Sinónimos que un revisor razonable puede escribir. Los subtítulos los genera y alinea el agente de voz.
_AGENT_ALIASES = {
    "script": "scriptwriter", "guion": "scriptwriter", "guionista": "scriptwriter", "writer": "scriptwriter",
    "subtitles": "voice", "subtitulos": "voice", "captions": "voice", "voz": "voice", "narracion": "voice",
    "audio": "sound", "sonido": "sound", "music": "sound", "musica": "sound", "mix": "sound",
    "video": "editor", "montaje": "editor", "animator": "editor", "animador": "editor", "render": "editor",
    "images": "resources", "imagenes": "resources", "recursos": "resources", "visuals": "resources",
    "direccion": "director",
}


def normalize_agent(value: object) -> object:
    if not isinstance(value, str):
        return value
    key = "".join(c for c in unicodedata.normalize("NFKD", value.strip().lower()) if not unicodedata.combining(c))
    return _AGENT_ALIASES.get(key, key)


class EditorialIssue(BaseModel):
    target_agent: TargetAgent = Field(description="Agente responsable de corregirlo")
    scene_index: int | None = None
    reason: str
    severity: Literal["minor", "major", "critical"] = "major"

    @field_validator("target_agent", mode="before")
    @classmethod
    def _normalize(cls, v: object) -> object:
        return normalize_agent(v)

    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v


class EditorialReview(BaseModel):
    scores: EditorialScores
    issues: list[EditorialIssue] = Field(default_factory=list)
    summary: str


from ..core.retention import QualityCheck as Check, retention_checks  # noqa: E402


# Solo el contenido creativo se mejora de forma automática cuando la nota ya es apta: repetir un cálculo
# determinista (audio, montaje) da el mismo resultado, y replantear todo (director) sería demasiado caro.
CONTENT_AGENTS = {"scriptwriter", "resources"}
AGENT_PHASE = {
    "director": "creative_direction", "scriptwriter": "script", "resources": "resource_generation",
    "voice": "voice", "editor": "edit", "sound": "sound",
}


def technical_checks(probe, voice: VoiceManifest, spec_fps: int) -> list[Check]:
    c: list[Check] = []
    d = probe.duration_s
    c.append(Check(name="duración", passed=MIN_DURATION_S <= d <= MAX_DURATION_S, points=0, max_points=6,
                   detail=f"{d:.2f}s (rango {MIN_DURATION_S}-{MAX_DURATION_S})", target_agent="voice",
                   critical=not MIN_DURATION_S <= d <= MAX_DURATION_S))
    c.append(Check(name="resolución", passed=(probe.width, probe.height) == (EXPECTED_W, EXPECTED_H), points=0,
                   max_points=5, detail=f"{probe.width}x{probe.height}", target_agent="editor",
                   critical=(probe.width, probe.height) != (EXPECTED_W, EXPECTED_H)))
    c.append(Check(name="códecs", passed=probe.video_codec == "h264" and probe.audio_codec == "aac", points=0,
                   max_points=3, detail=f"{probe.video_codec}/{probe.audio_codec}", target_agent="editor"))
    c.append(Check(name="fps", passed=probe.fps is not None and abs(probe.fps - spec_fps) < 0.5, points=0,
                   max_points=2, detail=f"{probe.fps}", target_agent="editor"))
    lufs_ok = probe.integrated_lufs is not None and -16.5 <= probe.integrated_lufs <= -11.5
    c.append(Check(name="sonoridad", passed=lufs_ok, points=0, max_points=5,
                   detail=f"{probe.integrated_lufs} LUFS (objetivo −14)", target_agent="sound"))
    peak_ok = probe.true_peak_db is not None and probe.true_peak_db <= -0.5
    c.append(Check(name="saturación", passed=peak_ok, points=0, max_points=3,
                   detail=f"pico {probe.true_peak_db} dBTP", target_agent="sound"))
    black = sum(e - s for s, e in probe.black_segments)
    c.append(Check(name="fotogramas negros", passed=black < 0.5, points=0, max_points=3,
                   detail=f"{black:.2f}s", target_agent="resources",
                   critical=black > 0.1 * max(d, 1.0)))
    frozen = max((e - s for s, e in probe.frozen_segments), default=0.0)
    c.append(Check(name="imagen congelada", passed=frozen < 5.0, points=0, max_points=2,
                   detail=f"máx {frozen:.1f}s", target_agent="editor"))
    long_silence = max((e - s for s, e in probe.silence_segments), default=0.0)
    c.append(Check(name="silencios", passed=long_silence < 2.0, points=0, max_points=1,
                   detail=f"máx {long_silence:.1f}s", target_agent="voice"))
    for ch in c:
        ch.points = ch.max_points if ch.passed else 0.0
    return c


def sync_checks(voice: VoiceManifest, video_duration_s: float) -> list[Check]:
    c: list[Check] = []
    drift = abs(video_duration_s - voice.total_duration_s)
    c.append(Check(name="sincronía audio/vídeo", passed=drift <= 0.25, points=0, max_points=6,
                   detail=f"desfase {drift:.2f}s", target_agent="editor"))
    bad_cues = 0
    for cue in voice.cues:
        owner = next((s for s in voice.scenes if s.start_s - 0.05 <= cue.start_s < s.start_s + s.scene_duration_s), None)
        if owner is None or cue.end_s > owner.start_s + owner.scene_duration_s + 0.05 or cue.end_s <= cue.start_s:
            bad_cues += 1
    c.append(Check(name="subtítulos dentro de su escena", passed=bad_cues == 0 and bool(voice.cues), points=0,
                   max_points=5, detail=f"{bad_cues} subtítulos fuera de rango de {len(voice.cues)}",
                   target_agent="voice"))
    overlaps = sum(1 for a, b in zip(voice.cues, voice.cues[1:]) if b.start_s < a.end_s - 0.01)
    c.append(Check(name="subtítulos sin solapes", passed=overlaps == 0, points=0, max_points=4,
                   detail=f"{overlaps} solapes", target_agent="voice"))
    for ch in c:
        ch.points = ch.max_points if ch.passed else 0.0
    return c


TASK = """Eres el revisor independiente de vídeos cortos verticales, con criterio de productor de contenido viral.
Evalúa con rigor el guion y los subtítulos finales (0-10 por criterio). Señala problemas concretos indicando el
agente responsable y la escena, y cómo arreglarlo. No inventes problemas: si algo está bien, puntúalo alto.
No predices viralidad: evalúas oficio.
Criterios:
- hook: en 1-2 s hay una razón para quedarse (pregunta, contradicción, imagen inesperada); sin saludos ni rodeos.
- pacing: cada escena aporta algo nuevo; hay re-ganchos o cambios de patrón y no hay relleno ni repeticiones.
- coherence: la historia avanza con lógica y el cierre resuelve (si cierra en bucle, conecta con el inicio).
- payoff: el vídeo cumple lo que promete el gancho; sin clickbait engañoso; la llamada a la acción es natural.
- spelling: ortografía y gramática. legibility: líneas de subtítulo cortas y legibles en móvil."""


class ReviewerAgent(Agent):
    name = "reviewer"
    title = "Revisor"
    phases = frozenset({"review"})
    uses_claude = True

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        threshold = ctx.settings.get("review_threshold", DEFAULT_THRESHOLD)
        script = ctx.workspace.load("scripts", "script", Script)
        voice = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
        preview = ctx.workspace.dir("review") / "master_preview.mp4"
        self.progress(ctx, phase, 0.1, "Análisis técnico")
        probe = ctx.providers.query(ProviderCategory.RENDERING, "probe", Path(preview), True, project_id=ctx.project_id)
        edit = ctx.workspace.load("scenes", "edit_manifest", EditManifest)
        checks = (technical_checks(probe, voice, ctx.spec.fps) + sync_checks(voice, probe.duration_s)
                  + retention_checks(voice, edit, ctx.narrative, ctx.spec.intensity))

        self.progress(ctx, phase, 0.5, "Revisión editorial")
        editorial = self.ask_llm(
            ctx, phase=phase, task=TASK, output_model=EditorialReview,
            context={
                "language": ctx.spec.language,
                "script": script.model_dump(mode="json", include={"hook", "closing", "call_to_action", "scenes",
                                                                  "retention_beats"}),
                "subtitles": [c.text for c in voice.cues][:200],
                "technical_summary": [f"{c.name}: {'OK' if c.passed else 'FALLO'} ({c.detail})" for c in checks],
            },
        )
        s = editorial.scores
        editorial_points = (s.hook * 1.2 + s.pacing + s.coherence * 0.6 + s.payoff * 0.4
                            + s.spelling * 0.4 + s.legibility * 0.4)  # máx 40
        technical_points = sum(c.points for c in checks)  # técnica 30 + sincronía 15 + retención 15
        score = round(technical_points + editorial_points)

        corrections: list[CorrectionRequest] = []
        for c in checks:
            if not c.passed and c.target_agent:
                corrections.append(CorrectionRequest(target_agent=c.target_agent, phase=AGENT_PHASE[c.target_agent],
                                                     reason=f"{c.name}: {c.detail}", scene_index=c.scene_index,
                                                     severity="critical" if c.critical else "major"))
        actionable: list[CorrectionRequest] = []  # graves y de contenido: regenerar sí cambia el resultado
        for issue in editorial.issues:
            if issue.target_agent in AGENT_PHASE and issue.severity in ("major", "critical"):
                if issue.target_agent in CONTENT_AGENTS:
                    actionable.append(CorrectionRequest(
                        target_agent=issue.target_agent, phase=AGENT_PHASE[issue.target_agent],
                        scene_index=issue.scene_index, reason=issue.reason, severity=issue.severity))
                corrections.append(CorrectionRequest(
                    target_agent=issue.target_agent, phase=AGENT_PHASE[issue.target_agent],
                    scene_index=issue.scene_index, reason=issue.reason,
                    severity="critical" if issue.severity == "critical" else "major",
                ))
        passed = score >= threshold and not any(c.severity == "critical" for c in corrections)
        round_no = len(list(ctx.workspace.dir("review").glob("review_*.json"))) + 1
        report = {
            "round": round_no, "score": score, "threshold": threshold, "passed": passed,
            "disclaimer": "Puntuación interna de calidad; no es una predicción de viralidad.",
            "technical": [c.model_dump() for c in checks],
            "editorial": editorial.model_dump(mode="json"),
            "corrections": [c.model_dump(mode="json") for c in corrections],
            "actionable": [c.model_dump(mode="json") for c in actionable],
            "probe": probe.model_dump(mode="json"),
        }
        path = ctx.workspace.save("review", f"review_{round_no}", report)
        ctx.workspace.save("review", "latest", report)
        return AgentResult(
            status="completed" if passed else "in_review",
            summary=f"Revisión {round_no}: {score}/100 (umbral {threshold}) — {'APTO' if passed else 'requiere correcciones'}",
            artifacts={"review": str(path)},
            corrections=[] if passed else corrections,
            metrics={"score": score, "passed": passed},
        )
