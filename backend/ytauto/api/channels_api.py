"""API de canales, licencias de Claude, entrevista del director y figuras por perfil."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..agents.briefing import ask_briefing
from ..agents.registry import AGENT_CLASSES
from ..app import App
from ..core.channels import Channel, channels
from ..core.models import ProjectStatus
from ..core.settings import REPO_ROOT
from ..core.theme import load_theme
from ..llm.licenses import LicenseError, LicenseInput, usage_stats, valid_license_id
from .board import ChannelBoards

LEGACY_FIGURES = REPO_ROOT / "assets" / "personajes"  # perfil gotham (recortes del render de Batman)
PROFILES_DIR = REPO_ROOT / "assets" / "perfiles"
_SLUG = re.compile(r"^[a-z0-9_-]{1,32}$")
MAX_UPLOAD = 12 * 1024 * 1024
AGENT_NAMES = [c.name for c in AGENT_CLASSES]


class BriefingIn(BaseModel):
    channel: str
    idea: str = Field(min_length=3, max_length=4000)


class LicenseMapIn(BaseModel):
    license_map: dict[str, str]
    resume: bool = True


def figures_dir(theme: str) -> Path:
    return LEGACY_FIGURES if theme == "gotham" and not (PROFILES_DIR / "gotham").is_dir() else PROFILES_DIR / theme


def read_figures(theme: str) -> dict[str, Any]:
    folder = figures_dir(theme)
    meta_path = folder / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, ValueError):
        meta = {}
    out = {}
    for name in AGENT_NAMES:
        if (folder / f"{name}.png").is_file():
            m = meta.get(name) or {}
            out[name] = {"anchor_x": float(m.get("anchor_x", 0.5)), "w": int(m.get("w", 200)), "h": int(m.get("h", 260))}
    return out


def save_figure(theme: str, agent: str, raw: bytes) -> dict[str, Any]:
    """Guarda una imagen subida como PNG del personaje (recorta márgenes transparentes) y actualiza meta.json."""
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(400, "El archivo no es una imagen válida (PNG, JPG o WebP)") from e
    img = img.convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    img.thumbnail((900, 900))
    folder = PROFILES_DIR / theme if theme != "gotham" else figures_dir(theme)
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{agent}.png")
    meta_path = folder / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, ValueError):
        meta = {}
    meta[agent] = {"anchor_x": 0.5, "w": img.width, "h": img.height}
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta[agent]


def register(api: FastAPI, app: App, deps: list, boards: ChannelBoards, schedule: Callable[[str], None]) -> None:
    A = deps

    def channel_or_404(cid: str) -> Channel:
        for c in channels():
            if c.id == cid:
                return c
        raise HTTPException(404, f"Canal inexistente: {cid}")

    def project_channels() -> dict[str, str]:
        out = {p.id: p.spec.channel for p in app.store.list_projects()}
        out.update({f"briefing-{c.id}": c.id for c in channels()})
        return out

    def persona(theme_id: str, agent: str) -> dict[str, Any] | None:
        p = load_theme(theme_id).persona(agent)
        return {"character": p.character, "glyph": p.glyph, "color": p.color} if p else None

    def require_licenses():
        if app.licenses is None:
            raise HTTPException(503, "Licencias no disponibles")
        return app.licenses

    # ------------------------------------------------------------ canales
    @api.get("/api/channels", dependencies=A)
    def list_channels() -> list[dict[str, Any]]:
        out = []
        for c in channels():
            th = load_theme(c.theme)
            out.append({**c.model_dump(), "accent": th.palette.accent, "room_title": th.room_title,
                        "director": persona(c.theme, "director"), "chief": persona(c.theme, "chief"),
                        "has_director_image": "director" in read_figures(c.theme)})
        return out

    @api.get("/api/overview", dependencies=A)
    def overview() -> dict[str, Any]:
        """Estado de todos los canales a la vez (para el panel general)."""
        projects = app.store.list_projects()
        usage = app.store.llm_usage()
        pch = project_channels()
        lic_all = app.licenses.list() if app.licenses else []
        out = []
        for c in channels():
            mine = [p for p in projects if p.spec.channel == c.id]
            by_status: dict[str, int] = {}
            for p in mine:
                by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            agents = boards.board(c.id).snapshot()
            running = [a for a in agents if a.status == "running"]
            current = next((p for p in mine if p.status is ProjectStatus.ACTIVE), None)
            tokens = sum(sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_tokens"))
                         for u in usage if pch.get(u["project_id"]) == c.id)
            lics = [x for x in lic_all if x.channel_id == c.id]
            out.append({
                "channel": c.model_dump(), "accent": load_theme(c.theme).palette.accent,
                "director": persona(c.theme, "director"),
                "projects": {"total": len(mine), "by_status": by_status},
                "current": {"id": current.id, "name": current.spec.name} if current else None,
                "running_agents": [{"name": a.name, "task": a.task, "progress": a.progress} for a in running],
                "waiting_agents": sum(1 for a in agents if a.status == "waiting"),
                "error_agents": sum(1 for a in agents if a.status == "error"),
                "tokens_total": tokens,
                "licenses": {"total": len(lics), "limited": sum(1 for x in lics if x.limited_now()),
                             "enabled": sum(1 for x in lics if x.enabled)},
            })
        return {"channels": out, "claude_slots": app.queue.lanes()["claude"].concurrency}

    # ------------------------------------------------------------ licencias
    @api.get("/api/licenses", dependencies=A)
    def list_licenses(channel: str | None = Query(None)) -> dict[str, Any]:
        store = require_licenses()
        stats = usage_stats(store.list(), app.store.llm_usage(), project_channels())
        if channel:
            stats["licenses"] = [x for x in stats["licenses"] if x["channel_id"] == channel]
        stats["channels"] = [c.model_dump() for c in channels()]
        stats["claude_slots"] = app.queue.lanes()["claude"].concurrency
        return stats

    @api.post("/api/licenses", dependencies=A, status_code=201)
    def create_license(body: LicenseInput) -> dict[str, Any]:
        channel_or_404(body.channel_id)
        try:
            lic = require_licenses().create(body)
        except LicenseError as e:
            raise HTTPException(400, str(e)) from e
        app.refresh_claude_slots()
        return lic.model_dump()

    @api.put("/api/licenses/{lid}", dependencies=A)
    def update_license(lid: str, body: LicenseInput) -> dict[str, Any]:
        channel_or_404(body.channel_id)
        if not valid_license_id(lid):
            raise HTTPException(404, "Licencia inexistente")
        try:
            lic = require_licenses().update(lid, body)
        except LicenseError as e:
            raise HTTPException(400, str(e)) from e
        app.refresh_claude_slots()
        return lic.model_dump()

    @api.delete("/api/licenses/{lid}", dependencies=A, status_code=204)
    def delete_license(lid: str) -> None:
        require_licenses().get(lid)
        require_licenses().delete(lid)
        app.refresh_claude_slots()

    @api.post("/api/licenses/{lid}/reset", dependencies=A)
    def reset_license(lid: str) -> dict[str, Any]:
        """El usuario confirma que la licencia vuelve a tener uso disponible."""
        store = require_licenses()
        store.get(lid)
        store.clear_limit(lid)
        app.worker.recover()  # reanuda los proyectos que esperaban a esta licencia
        return store.get(lid).model_dump()

    @api.get("/api/licenses/plan", dependencies=A)
    def license_plan(channel: str = Query(...), project: str | None = Query(None)) -> dict[str, Any]:
        """Qué licencia usará cada agente (la del proyecto si existe, si no la del canal)."""
        channel_or_404(channel)
        lmap = app.store.get_project(project).spec.license_map if project else {}
        plan = {}
        for name in AGENT_NAMES:
            lic = app.router.resolve_for(channel, lmap, name) if app.router else None
            plan[name] = lic.id if lic else None
        return {"plan": plan, "license_map": lmap}

    @api.put("/api/projects/{pid}/licenses", dependencies=A)
    def set_project_licenses(pid: str, body: LicenseMapIn) -> dict[str, Any]:
        rec = app.store.get_project(pid)
        unknown = set(body.license_map) - set(AGENT_NAMES)
        if unknown:
            raise HTTPException(400, f"Agentes desconocidos: {sorted(unknown)}")
        store = require_licenses()
        for lid in body.license_map.values():
            store.get(lid)
        rec.spec.license_map = dict(body.license_map)
        app.store.save_project(rec)
        resumed = False
        if body.resume and rec.status is ProjectStatus.BLOCKED and any(
                ph.blocked_code == "usage_limit" for ph in app.store.list_phases(pid)):
            app.orchestrator.resume(pid)
            schedule(pid)
            resumed = True
        return {"license_map": rec.spec.license_map, "resumed": resumed}

    # ------------------------------------------------------------ entrevista del director
    @api.post("/api/briefing", dependencies=A)
    def briefing(body: BriefingIn) -> dict[str, Any]:
        ch = channel_or_404(body.channel)
        model = app.models.for_agent("director")
        usage_holder: dict[str, Any] = {}

        def call(request):
            resp = app.router.complete_for(ch.id, {}, request) if app.router else app.llm.complete(request)
            usage_holder["u"] = resp.usage
            return resp

        base = app.router.default if app.router else app.llm
        result = ask_briefing(base, model, body.idea, ch.name, call=call)
        if "u" in usage_holder:
            app.store.record_llm_usage(f"briefing-{ch.id}", "director", "briefing", usage_holder["u"].model_dump())
        return {**result.model_dump(), "director": persona(ch.theme, "director")}

    # ------------------------------------------------------------ figuras por perfil
    @api.get("/api/profiles/{theme}/figures", dependencies=A)
    def profile_figures(theme: str) -> dict[str, Any]:
        if not _SLUG.match(theme):
            raise HTTPException(404, "Perfil inexistente")
        return read_figures(theme)

    @api.get("/api/profiles/{theme}/figures/{agent}.png", dependencies=A)
    def profile_figure(theme: str, agent: str) -> FileResponse:
        path = figures_dir(theme) / f"{agent}.png"
        if not _SLUG.match(theme) or agent not in AGENT_NAMES or not path.is_file():
            raise HTTPException(404, "Figura no disponible")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})

    @api.put("/api/profiles/{theme}/figures/{agent}", dependencies=A)
    async def upload_figure(theme: str, agent: str, request: Request) -> dict[str, Any]:
        """Sube la imagen de un personaje (cuerpo binario). Mejor PNG con fondo transparente."""
        if not _SLUG.match(theme) or agent not in AGENT_NAMES:
            raise HTTPException(404, "Perfil o agente inexistente")
        raw = await request.body()
        if not raw or len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "Imagen vacía o demasiado grande (máx. 12 MB)")
        return save_figure(theme, agent, raw)
