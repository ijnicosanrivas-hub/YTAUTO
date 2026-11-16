"""Agente 9 — Publicador: versiones por plataforma, metadatos, miniaturas y publicación autorizada."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..core.errors import PhaseBlocked, ProviderNotConfigured
from ..core.models import Script
from ..core.platforms import PlatformProfile, load_profiles
from ..core.thumbnail import compose_thumbnail
from ..core.timeline import SoundManifest, VoiceManifest, EditManifest
from ..providers.interfaces import FinalizeSpec, ProviderCategory, PublishRequest
from .base import Agent, AgentContext, AgentResult


class PlatformMetadata(BaseModel):
    platform: str
    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)


class PublishMetadata(BaseModel):
    items: list[PlatformMetadata]


def check_metadata(meta: PublishMetadata, profiles: dict[str, PlatformProfile], wanted: list[str]) -> list[str]:
    issues = []
    got = {m.platform for m in meta.items}
    if got != set(wanted):
        issues.append(f"Debe haber metadatos exactamente para {sorted(wanted)}")
    for m in meta.items:
        p = profiles.get(m.platform)
        if not p:
            continue
        lim = p.metadata
        if p.metadata.title_required and not m.title.strip():
            issues.append(f"{m.platform}: el título es obligatorio")
        if len(m.title) > lim.title_max_chars:
            issues.append(f"{m.platform}: título de {len(m.title)} caracteres (máx {lim.title_max_chars})")
        if len(m.description) > lim.description_max_chars:
            issues.append(f"{m.platform}: descripción demasiado larga")
        if len(m.hashtags) > lim.hashtags_max:
            issues.append(f"{m.platform}: {len(m.hashtags)} hashtags (máx {lim.hashtags_max})")
        if any(" " in h for h in m.hashtags):
            issues.append(f"{m.platform}: los hashtags no pueden contener espacios")
    return issues


TASK = """Eres el responsable de publicación de vídeos cortos. Para cada plataforma de
`platforms`, redacta título, descripción y hashtags en el idioma `language`, adaptados al estilo de
cada red y respetando estrictamente sus límites (`limits`). Sin clickbait engañoso: el título debe
corresponder al contenido. Hashtags con '#', sin espacios, relevantes al tema."""


class PublisherAgent(Agent):
    name = "publisher"
    title = "Publicador"
    phases = frozenset({"exports", "publish_prep", "publish"})
    uses_claude = True

    def execute(self, phase: str, ctx: AgentContext) -> AgentResult:
        if phase == "exports":
            return self._exports(ctx)
        if phase == "publish_prep":
            return self._prep(ctx)
        return self._publish(ctx)

    def _profiles(self, ctx: AgentContext) -> dict[str, PlatformProfile]:
        profiles = load_profiles(ctx.settings.get("platforms_dir"))
        missing = [p.value for p in ctx.spec.platforms if p.value not in profiles]
        if missing:
            raise PhaseBlocked(f"Faltan perfiles de plataforma: {missing}", code="config")
        return {p.value: profiles[p.value] for p in ctx.spec.platforms}

    # ------------------------------------------------------------------ fase 15
    def _exports(self, ctx: AgentContext) -> AgentResult:
        profiles = self._profiles(ctx)
        edit = ctx.workspace.load("scenes", "edit_manifest", EditManifest)
        sound = ctx.workspace.load("sound", "sound_manifest", SoundManifest)
        voice = ctx.workspace.load("voice", "voice_manifest", VoiceManifest)
        script = ctx.workspace.load("scripts", "script", Script)
        exports, problems = {}, []
        for n, (pid, prof) in enumerate(profiles.items()):
            self.progress(ctx, "exports", n / len(profiles), prof.display_name)
            out = ctx.workspace.dir("exports") / f"{pid}.mp4"
            enc = prof.encode.model_copy(update={"fps": ctx.spec.fps})
            # Se parte de los mismos segmentos y mezcla: no se regeneran recursos.
            ctx.providers.invoke(
                ProviderCategory.RENDERING, "finalize",
                FinalizeSpec(video_path=Path(edit.video_path), audio_path=Path(sound.mix_path),
                             subtitles=voice.cues, subtitle_style=prof.subtitles, profile=enc,
                             metadata={"title": script.internal_title}, out_path=out),
                project_id=ctx.project_id,
            )
            probe = ctx.providers.query(ProviderCategory.RENDERING, "probe", out, False)
            if not prof.min_duration_s <= probe.duration_s <= prof.max_duration_s:
                problems.append(f"{pid}: duración {probe.duration_s:.1f}s fuera de perfil")
            if (probe.width, probe.height) != (enc.width, enc.height):
                problems.append(f"{pid}: resolución {probe.width}x{probe.height}")
            exports[pid] = {"path": str(out), "duration_s": probe.duration_s, "size_bytes": probe.size_bytes,
                            "profile_verified_at": prof.verified_at}
        path = ctx.workspace.save("exports", "exports", exports)
        if problems:
            raise PhaseBlocked("; ".join(problems), code="export_validation")
        return AgentResult(summary=f"Exportaciones: {', '.join(exports)}", artifacts={"exports": str(path)})

    # ------------------------------------------------------------------ fase 16
    def _prep(self, ctx: AgentContext) -> AgentResult:
        profiles = self._profiles(ctx)
        script = ctx.workspace.load("scripts", "script", Script)
        meta = self.ask_llm(
            ctx, phase="publish_prep", task=TASK, output_model=PublishMetadata,
            context={
                "language": ctx.spec.language, "topic": ctx.spec.topic, "hook": script.hook,
                "summary": [s.narration for s in script.scenes][:20],
                "platforms": list(profiles),
                "limits": {k: v.metadata.model_dump() for k, v in profiles.items()},
            },
            accept=lambda m: check_metadata(m, profiles, list(profiles)),
        )
        # Miniatura: fotograma del gancho + título (composición local).
        master = ctx.workspace.dir("exports") / "master_clean.mp4"
        frame = ctx.workspace.dir("exports") / "thumb_frame.png"
        ctx.providers.query(ProviderCategory.RENDERING, "extract_frame", master, 1.0, frame)
        thumbs = {}
        for item in meta.items:
            prof = profiles[item.platform]
            if prof.thumbnail.get("supported", False):
                thumbs[item.platform] = str(compose_thumbnail(
                    frame, item.title or script.internal_title,
                    ctx.workspace.dir("exports") / f"{item.platform}_thumb.jpg",
                    safe_top=prof.safe_area.get("top", 220)))
        package = {m.platform: m.model_dump() | {"thumbnail": thumbs.get(m.platform)} for m in meta.items}
        path = ctx.workspace.save("exports", "publish_package", package)
        return AgentResult(status="in_review", summary=f"Metadatos y miniaturas para {', '.join(package)}",
                           artifacts={"publish_package": str(path)})

    # ------------------------------------------------------------------ fase 17
    def _publish(self, ctx: AgentContext) -> AgentResult:
        package = ctx.workspace.load("exports", "publish_package")
        exports = ctx.workspace.load("exports", "exports")
        auths: dict[str, str] = ctx.settings.get("publish_authorizations", {})
        results = {}
        for platform, meta in package.items():
            auth = auths.get(platform)
            if not auth:
                results[platform] = {"status": "skipped", "message": "Sin autorización expresa del usuario"}
                continue
            req = PublishRequest(platform=platform, video_path=Path(exports[platform]["path"]),
                                 title=meta["title"], description=meta["description"], hashtags=meta["hashtags"],
                                 thumbnail_path=Path(meta["thumbnail"]) if meta.get("thumbnail") else None,
                                 privacy=ctx.settings.get("publish_privacy", "private"), authorization_id=auth)
            try:
                res = ctx.providers.invoke(ProviderCategory.PUBLISHING, "publish", req, project_id=ctx.project_id)
                results[platform] = res.model_dump(mode="json")
            except ProviderNotConfigured as e:
                results[platform] = {"status": "manual_package", "message": f"Sin integración configurada: {e}. "
                                     "Material listo en exports/ para publicación manual."}
        path = ctx.workspace.save("exports", "publish_results", results)
        done = [p for p, r in results.items() if r.get("status") in ("published", "uploaded_private")]
        return AgentResult(summary=f"Publicación: {len(done)} publicadas; resto preparado o sin autorización",
                           artifacts={"publish_results": str(path)}, metrics={"results": results})
