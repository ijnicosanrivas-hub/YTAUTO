"""Agente 9 — Publicador: versiones por plataforma, metadatos, miniaturas y publicación autorizada."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from ..core.captions import PublishFields, compose, fit_hashtags, validate_fields
from ..core.errors import PhaseBlocked, ProviderError, ProviderNotConfigured
from ..core.export_validation import validate_export
from ..core.models import Script
from ..core.platforms import PlatformProfile, load_profiles
from ..core.thumbnail import compose_thumbnail
from ..core.timeline import EditManifest, SoundManifest, VoiceManifest
from ..core.workspace import sha256_file, stable_hash
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
    """Valida los textos tal y como se publicarán (compuestos y medidos como lo hace cada plataforma)."""
    issues = []
    got = {m.platform for m in meta.items}
    if got != set(wanted):
        issues.append(f"Debe haber metadatos exactamente para {sorted(wanted)}")
    for m in meta.items:
        p = profiles.get(m.platform)
        if not p:
            continue
        fields = compose(p, m.title, m.description, m.hashtags)
        issues += [f"{m.platform}: {i}" for i in validate_fields(p, fields)]
    return issues


TASK = """Eres el responsable de publicación de vídeos cortos. Para cada plataforma de
`platforms`, redacta título, descripción y hashtags en el idioma `language`, adaptados al estilo de
cada red y respetando estrictamente sus límites (`limits`, `rules`). Sin clickbait engañoso: el título debe
corresponder al contenido. Hashtags con '#', sin espacios, relevantes al tema. Las reglas de medición
varían: YouTube mide la descripción en bytes UTF-8; Instagram y TikTok meten los hashtags dentro del pie."""

MANUAL_README = """PUBLICACIÓN MANUAL — {display_name}
=====================================

Archivos de esta carpeta:
  video.mp4          vídeo exportado para {display_name}
  {thumb_line}
  publicacion.json   textos listos para pegar

Texto a publicar
----------------
{text_block}

Limitaciones de la publicación automática
-----------------------------------------
{notes}

Perfil verificado con documentación oficial el {verified}.
Valores NO verificados (revísalos en la vista previa de la app): {unverified}
"""


def _link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.link(src, dst)  # sin duplicar el espacio en disco
    except OSError:
        shutil.copy2(src, dst)


YT_MUSIC_OFF_PLATFORM = ("La música viene de la Biblioteca de audio de YouTube: es segura en YouTube, pero YouTube no "
                         "garantiza su uso fuera de su plataforma. Revisa la licencia de la pista antes de publicar aquí.")


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
        previous = ctx.workspace.load("exports", "exports") if ctx.workspace.has("exports", "exports") else {}
        # Huella de las entradas compartidas por todas las versiones: el máster y la mezcla.
        base = [sha256_file(Path(edit.video_path)), sha256_file(Path(sound.mix_path)),
                [c.model_dump(mode="json") for c in voice.cues]]
        exports: dict[str, dict] = {}
        problems: list[str] = []
        reused = 0
        for n, (pid, prof) in enumerate(profiles.items()):
            self.progress(ctx, "exports", n / len(profiles), prof.display_name)
            out = ctx.workspace.dir("exports") / f"{pid}.mp4"
            enc = prof.encode.model_copy(update={"fps": ctx.spec.fps})
            style = (prof.subtitles.model_copy(update={"mode": ctx.spec.subtitle_mode})
                     if ctx.spec.subtitle_mode else prof.subtitles)
            key = stable_hash([base, enc.model_dump(mode="json"), style.model_dump(mode="json"),
                               script.internal_title])
            if out.exists() and previous.get(pid, {}).get("input_hash") == key:
                reused += 1  # mismas entradas: no se vuelve a codificar
            else:
                # Se parte del mismo máster y la misma mezcla: no se regenera ningún recurso.
                ctx.providers.invoke(
                    ProviderCategory.RENDERING, "finalize",
                    FinalizeSpec(video_path=Path(edit.video_path), audio_path=Path(sound.mix_path),
                                 subtitles=voice.cues, profile=enc, subtitle_style=style,
                                 metadata={"title": script.internal_title}, out_path=out),
                    project_id=ctx.project_id,
                )
            probe = ctx.providers.query(ProviderCategory.RENDERING, "probe", out, False, project_id=ctx.project_id)
            validation = validate_export(probe, prof)
            problems += [f"{pid}: {i.message}" for i in validation.errors]
            exports[pid] = {
                "path": str(out), "duration_s": probe.duration_s, "size_bytes": probe.size_bytes,
                "width": probe.width, "height": probe.height, "fps": probe.fps,
                "video_codec": probe.video_codec, "audio_codec": probe.audio_codec,
                "profile_verified_at": prof.verified_at, "input_hash": key,
                "validation": validation.model_dump(mode="json"),
            }
        path = ctx.workspace.save("exports", "exports", exports)
        if problems:
            raise PhaseBlocked("Exportación no válida: " + "; ".join(problems), code="export_validation")
        warns = sum(len(v["validation"]["issues"]) for v in exports.values())
        return AgentResult(
            summary=f"Exportaciones validadas: {', '.join(exports)} ({reused} reutilizadas)"
                    + (f", {warns} avisos" if warns else ""),
            artifacts={"exports": str(path)}, metrics={"reused": reused, "encoded": len(exports) - reused},
        )

    # ------------------------------------------------------------------ fase 16
    def _prep(self, ctx: AgentContext) -> AgentResult:
        profiles = self._profiles(ctx)
        script = ctx.workspace.load("scripts", "script", Script)
        exports = ctx.workspace.load("exports", "exports")
        meta = self.ask_llm(
            ctx, phase="publish_prep", task=TASK, output_model=PublishMetadata,
            context={
                "language": ctx.spec.language, "topic": ctx.spec.topic, "hook": script.hook,
                "summary": [s.narration for s in script.scenes][:20],
                "platforms": list(profiles),
                "limits": {k: v.metadata.model_dump() for k, v in profiles.items()},
                "rules": {k: v.metadata.mode for k, v in profiles.items()},
            },
            accept=lambda m: check_metadata(m, profiles, list(profiles)),
        )
        # Miniatura: fotograma del gancho + título (composición local), solo si la plataforma la admite.
        master = ctx.workspace.dir("exports") / "master_clean.mp4"
        frame = ctx.workspace.dir("exports") / "thumb_frame.png"
        ctx.providers.query(ProviderCategory.RENDERING, "extract_frame", master, 1.0, frame,
                            project_id=ctx.project_id)
        credit, yt_music = self._music_credit(ctx)
        package: dict[str, dict] = {}
        for item in meta.items:
            prof = profiles[item.platform]
            description = item.description
            if credit and credit not in description:
                # Licencia Creative Commons: el crédito al artista es obligatorio en la descripción.
                description = f"{description.rstrip()}\n\n🎵 {credit}".strip()
            fields = fit_hashtags(prof, item.title, description, item.hashtags)
            thumb = None
            if prof.thumbnail.get("supported", False):
                thumb = str(compose_thumbnail(
                    frame, item.title or script.internal_title,
                    ctx.workspace.dir("exports") / f"{item.platform}_thumb.jpg",
                    safe_top=prof.safe_area.get("top", 220)))
            extra = [YT_MUSIC_OFF_PLATFORM] if yt_music and item.platform != "youtube_shorts" else []
            manual = self._manual_package(ctx, prof, fields, Path(exports[item.platform]["path"]), thumb, extra)
            package[item.platform] = {
                "title": fields.title or item.title, "description": fields.description or fields.caption or "",
                "hashtags": fields.hashtags, "thumbnail": thumb, "fields": fields.model_dump(mode="json"),
                "issues": validate_fields(prof, fields), "manual_dir": str(manual),
                "publish_notes": [*prof.publish.notes, *extra],
                "music_credit": credit, "unaudited_private_only": prof.publish.unaudited_private_only,
                "privacy_options": prof.publish.privacy_options,
                "public_url_required": prof.publish.public_url_required,
                "profile_verified_at": prof.verified_at,
            }
        path = ctx.workspace.save("exports", "publish_package", package)
        return AgentResult(status="in_review",
                           summary=f"Metadatos, miniaturas y paquetes manuales para {', '.join(package)}",
                           artifacts={"publish_package": str(path)})

    @staticmethod
    def _music_credit(ctx: AgentContext) -> tuple[str | None, bool]:
        """(crédito obligatorio de la música, ¿es de la Biblioteca de audio de YouTube?)."""
        try:
            sound = ctx.workspace.load("sound", "sound_manifest", SoundManifest)
        except Exception:  # noqa: BLE001 - sin mezcla registrada no hay crédito que añadir
            return None, False
        return sound.music_credit, sound.music_provider == "youtube_audio_library"

    def _manual_package(self, ctx: AgentContext, prof: PlatformProfile, fields: PublishFields, video: Path,
                        thumb: str | None, extra_notes: list[str] | None = None) -> Path:
        """Carpeta lista para publicar a mano (también cuando la API oficial no lo permite)."""
        d = ctx.workspace.dir("exports") / "manual" / prof.id
        _link_or_copy(video, d / "video.mp4")
        if thumb:
            _link_or_copy(Path(thumb), d / "miniatura.jpg")
        text = [f"Título: {fields.title}"] if fields.title and fields.title != fields.caption else []
        text.append(fields.description or fields.caption or "")
        notes = "\n".join(f"- {n}" for n in [*prof.publish.notes, *(extra_notes or [])]) or "- Ninguna conocida."
        (d / "LEEME.txt").write_text(MANUAL_README.format(
            display_name=prof.display_name, thumb_line="miniatura.jpg     miniatura propuesta" if thumb else
            "(esta plataforma no usa miniatura propia en su API)", text_block="\n".join(text), notes=notes,
            verified=prof.verified_at or "nunca", unverified=", ".join(prof.unverified) or "ninguno"),
            encoding="utf-8")
        (d / "publicacion.json").write_text(fields.model_dump_json(indent=2), encoding="utf-8")
        return d

    # ------------------------------------------------------------------ fase 17
    def _publish(self, ctx: AgentContext) -> AgentResult:
        """Publica SOLO donde hay autorización vigente, con la visibilidad autorizada.

        - Lo ya publicado no se repite (los reintentos no duplican publicaciones).
        - Si la API no permite algo, se explica la limitación y queda el paquete manual.
        - Si una publicación autorizada falla, la fase se bloquea con el motivo; lo ya publicado se conserva.
        """
        profiles = self._profiles(ctx)
        package = ctx.workspace.load("exports", "publish_package")
        exports = ctx.workspace.load("exports", "exports")
        previous = ctx.workspace.load("exports", "publish_results") if ctx.workspace.has("exports", "publish_results") else {}
        auths: dict[str, str] = ctx.settings.get("publish_authorizations", {})
        privacy_by = ctx.settings.get("publish_privacy_by_platform", {})
        results: dict[str, dict] = {}
        failed: list[str] = []
        for platform, meta in package.items():
            manual = meta.get("manual_dir")
            prof = profiles.get(platform)
            prev = previous.get(platform, {})
            if prev.get("status") in ("published", "uploaded_private"):
                results[platform] = prev  # ya publicado: no se repite
                continue
            auth = auths.get(platform)
            if not auth:
                results[platform] = {"status": "skipped", "message": "Sin autorización expresa del usuario",
                                     "package_path": manual}
                continue
            privacy = privacy_by.get(platform, ctx.settings.get("publish_privacy", "private"))
            if prof and privacy not in prof.publish.privacy_options:
                results[platform] = {"status": "manual_package", "package_path": manual, "message": (
                    f"{prof.display_name} no admite la visibilidad «{privacy}» por API "
                    f"(opciones: {', '.join(prof.publish.privacy_options)}). Material listo para publicación manual.")}
                continue
            f = meta.get("fields") or {}
            video = Path(exports[platform]["path"])
            req = PublishRequest(platform=platform, video_path=video, title=f.get("title") or meta["title"],
                                 description=f.get("description") or f.get("caption") or meta["description"],
                                 hashtags=meta["hashtags"], privacy=privacy, authorization_id=auth,
                                 thumbnail_path=Path(meta["thumbnail"]) if meta.get("thumbnail") else None)
            if prof and prof.publish.public_url_required and privacy == "public":
                req.video_url = self._public_url(ctx, video, platform)  # solo con autorización pública explícita
            try:
                limits = ctx.providers.invoke(ProviderCategory.PUBLISHING, "check_requirements", req,
                                              project_id=ctx.project_id)
                if limits:
                    results[platform] = {"status": "manual_package", "package_path": manual,
                                         "message": "La publicación automática no es posible: " + "; ".join(limits)
                                                    + ". Material listo para publicación manual."}
                    continue
                res = ctx.providers.invoke(ProviderCategory.PUBLISHING, "publish", req, project_id=ctx.project_id)
                results[platform] = res.model_dump(mode="json") | {"package_path": manual}
            except ProviderNotConfigured as e:
                results[platform] = {"status": "manual_package", "package_path": manual,
                                     "message": f"Sin integración configurada: {e}. "
                                                "Material listo en exports/manual/ para publicación manual."}
            except ProviderError as e:
                results[platform] = {"status": "failed", "message": str(e), "package_path": manual}
                failed.append(f"{platform}: {e}")
        path = ctx.workspace.save("exports", "publish_results", results)
        if failed:  # se guarda todo lo hecho y se bloquea con el motivo: «Reintentar» omite lo ya publicado
            raise PhaseBlocked("Fallo al publicar: " + " | ".join(failed), code="publish_failed")
        done = [p for p, r in results.items() if r.get("status") in ("published", "uploaded_private")]
        return AgentResult(summary=f"Publicación: {len(done)} publicadas; resto preparado o sin autorización",
                           artifacts={"publish_results": str(path)}, metrics={"results": results})

    def _public_url(self, ctx: AgentContext, video: Path, platform: str) -> str | None:
        """URL pública del vídeo si hay un almacenamiento que la ofrezca (si no, None → paquete manual)."""
        try:
            key = f"{ctx.project_id}/{platform}.mp4"
            ctx.providers.query(ProviderCategory.STORAGE, "put", video, key, project_id=ctx.project_id)
            return ctx.providers.query(ProviderCategory.STORAGE, "public_url", key, project_id=ctx.project_id)
        except (ProviderNotConfigured, ProviderError):
            return None
