"""API REST + WebSocket de la sala de producción.

Por defecto escucha solo en 127.0.0.1. Si se define `YTAUTO_API_TOKEN`, todas las rutas
(y el WebSocket) exigen `Authorization: Bearer <token>` o `?token=<token>`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..app import App
from ..core.events import Event
from ..core.models import PhaseStatus, ProjectSpec
from ..core.settings import REPO_ROOT
from ..core.workspace import Workspace
from ..orchestrator.pipeline import PHASES, PIPELINE
from ..providers.interfaces import ProviderCategory
from ..providers.registry import RegistryError
from .board import Board, rebuild

log = logging.getLogger("ytauto.api")
MODEL_RE = re.compile(r"^(sonnet|opus|haiku|claude-[a-z0-9\-\.]+)$")
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


# ---------------------------------------------------------------- esquemas de entrada
class ApproveIn(BaseModel):
    gate: str
    approved: bool = True
    note: str = ""


class RedoIn(BaseModel):
    scenes: list[int]
    from_phase: str = "resource_generation"
    reason: str = ""


class ProviderIn(BaseModel):
    adapter: str
    id: str | None = None
    display_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    monthly_budget_eur: float | None = None
    max_generations_per_project: int | None = None


class ProviderPatch(BaseModel):
    display_name: str | None = None
    enabled: bool | None = None
    params: dict[str, Any] | None = None
    monthly_budget_eur: float | None = None
    max_generations_per_project: int | None = None


class CredentialIn(BaseModel):
    key: str = "api_key"
    value: str = Field(min_length=1)


class OrderIn(BaseModel):
    category: ProviderCategory
    ids: list[str]


class BudgetIn(BaseModel):
    monthly_budget_eur: float | None = Field(default=None, ge=0)
    warn_fraction: float | None = Field(default=None, gt=0, le=1)
    spend_authorized_providers: list[str] | None = None


class ModelsIn(BaseModel):
    default: str | None = None
    fallback: str | None = None
    agents: dict[str, str] = Field(default_factory=dict)


class ConcurrencyIn(BaseModel):
    lane: str
    concurrency: int = Field(ge=1, le=8)


# ---------------------------------------------------------------- utilidades
def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _project_view(app: App, pid: str) -> dict[str, Any]:
    try:
        proj = app.store.get_project(pid)
    except KeyError as e:
        raise HTTPException(404, "Proyecto inexistente") from e
    phases = app.store.list_phases(pid)
    nxt = app.orchestrator.next_phase(pid)
    waiting = [p.phase for p in phases if p.status is PhaseStatus.IN_REVIEW and PHASES[p.phase].kind == "approval"]
    if nxt and nxt.id == "publish" and app.store.get_phase(pid, "publish").blocked_code == "publish_authorization":
        waiting.append("publish")
    done = sum(1 for p in phases if p.status.is_done)
    return {
        "project": proj.model_dump(mode="json"),
        "progress": round(done / len(phases), 3),
        "next_phase": nxt.id if nxt else None,
        "waiting_approval": waiting,
        "phases": [p.model_dump(mode="json") | {"number": PHASES[p.phase].number, "title": PHASES[p.phase].title,
                                                "agent": PHASES[p.phase].agent, "kind": PHASES[p.phase].kind}
                   for p in phases],
    }


def create_api(app: App, start_worker: bool = False, token: str | None = None,
               allowed_origins: list[str] | None = None) -> FastAPI:
    token = token if token is not None else os.environ.get("YTAUTO_API_TOKEN") or None
    board = Board()
    rebuild(board, app.store.events(limit=2000))
    clients: set[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = set()
    clients_lock = threading.Lock()

    def on_event(e: Event) -> None:
        state = board.apply(e)
        msg = {"event": e.model_dump(mode="json"), "agent": state.model_dump(mode="json") if state else None}
        with clients_lock:
            targets = list(clients)
        for q, loop in targets:
            try:
                loop.call_soon_threadsafe(q.put_nowait, msg)
            except RuntimeError:
                pass  # bucle cerrado

    app.events.subscribe(on_event)
    worker_thread: threading.Thread | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal worker_thread
        if start_worker:
            worker_thread = threading.Thread(target=app.worker.run_forever, name="ytauto-worker", daemon=True)
            worker_thread.start()
        yield
        if start_worker and worker_thread:
            app.worker.stop()
            # Apagado ordenado: se espera a la tarea en curso; si no termina, su lease caduca en minutos.
            worker_thread.join(timeout=float(os.environ.get("YTAUTO_SHUTDOWN_GRACE_S", "20")))

    api = FastAPI(title="YTAUTO — Sala de producción", version="0.1.0", lifespan=lifespan)
    api.add_middleware(CORSMiddleware, allow_origins=allowed_origins or ["http://localhost:5173",
                                                                         "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    def auth(request: Request) -> None:
        if not token:
            return
        header = request.headers.get("authorization", "")
        if header != f"Bearer {token}" and request.query_params.get("token") != token:
            raise HTTPException(401, "Token requerido")

    A = [Depends(auth)]

    def schedule(pid: str) -> None:
        try:
            app.worker.schedule(pid)
        except Exception:  # noqa: BLE001
            log.exception("No se pudo planificar %s", pid)

    # ------------------------------------------------------------ estado general
    @api.get("/api/health")
    def health() -> dict[str, Any]:
        ok, msg = app.llm.health_check()
        return {"ok": True, "llm": {"provider": app.llm.name, "ok": ok, "message": msg},
                "worker": bool(worker_thread and worker_thread.is_alive())}

    @api.get("/api/dashboard", dependencies=A)
    def dashboard() -> dict[str, Any]:
        projects = app.store.list_projects()
        by_status: dict[str, int] = {}
        for p in projects:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
        usage = app.store.llm_usage()
        waiting = []
        for p in projects[:50]:
            v = _project_view(app, p.id)
            if v["waiting_approval"]:
                waiting.append({"id": p.id, "name": p.spec.name, "gates": v["waiting_approval"]})
        budget = app.provider_system.budget.summary() if app.provider_system else None
        return {"projects": {"total": len(projects), "by_status": by_status},
                "waiting_approval": waiting,
                "claude": {"calls": len(usage), "seconds": round(sum(u.get("duration_s") or 0 for u in usage), 1),
                           "lanes": {k: v.model_dump() for k, v in app.queue.lanes().items()}},
                "queue": app.queue.stats(), "budget": budget,
                "agents": [a.model_dump() for a in board.snapshot()]}

    # ------------------------------------------------------------ proyectos
    @api.get("/api/projects", dependencies=A)
    def list_projects() -> list[dict[str, Any]]:
        out = []
        for p in app.store.list_projects():
            v = _project_view(app, p.id)
            out.append({"id": p.id, "name": p.spec.name, "topic": p.spec.topic, "status": p.status.value,
                        "duration_s": p.spec.duration_s, "progress": v["progress"], "next_phase": v["next_phase"],
                        "waiting_approval": v["waiting_approval"], "created_at": p.created_at,
                        "blocked_reason": p.blocked_reason})
        return out

    @api.post("/api/projects", dependencies=A, status_code=201)
    def create_project(spec: ProjectSpec) -> dict[str, Any]:
        pid = app.orchestrator.create_project(spec)
        schedule(pid)
        return _project_view(app, pid)

    @api.get("/api/projects/{pid}", dependencies=A)
    def get_project(pid: str) -> dict[str, Any]:
        view = _project_view(app, pid)
        ws = Workspace(app.settings.projects_dir, pid)
        view["memory"] = _read_json(ws.root / "memory.json")
        view["llm_usage"] = app.store.llm_usage(pid)
        view["costs"] = app.provider_system.budget.ledger(pid) if app.provider_system else []
        return view

    @api.get("/api/projects/{pid}/artifacts", dependencies=A)
    def artifacts(pid: str) -> dict[str, Any]:
        _project_view(app, pid)
        ws = Workspace(app.settings.projects_dir, pid)
        files = {"brief": ("planning", "creative_brief"), "script": ("scripts", "script"),
                 "prompts": ("resources", "prompts"), "assets": ("resources", "assets"),
                 "voice": ("voice", "voice_manifest"), "edit": ("scenes", "edit_manifest"),
                 "sound": ("sound", "sound_manifest"), "review": ("review", "latest"),
                 "exports": ("exports", "exports"), "publish_package": ("exports", "publish_package"),
                 "publish_results": ("exports", "publish_results"), "report": ("reports", "report")}
        out = {k: (ws.load(sub, name) if ws.has(sub, name) else None) for k, (sub, name) in files.items()}
        out["preview"] = "review/master_preview.mp4" if (ws.root / "review/master_preview.mp4").exists() else None
        out["master"] = "exports/master_clean.mp4" if (ws.root / "exports/master_clean.mp4").exists() else None
        return out

    @api.get("/api/projects/{pid}/files/{path:path}", dependencies=A)
    def project_file(pid: str, path: str) -> FileResponse:
        ws = Workspace(app.settings.projects_dir, pid)
        try:
            target = ws.resolve_inside(ws.root / path)
        except PermissionError as e:
            raise HTTPException(403, "Ruta no permitida") from e
        if not target.is_file():
            raise HTTPException(404, "Fichero inexistente")
        return FileResponse(target)  # admite peticiones Range (vídeo con búsqueda)

    @api.get("/api/projects/{pid}/events", dependencies=A)
    def project_events(pid: str, limit: int = Query(200, le=2000)) -> list[dict[str, Any]]:
        return app.store.events(pid, limit=limit)

    def _control(pid: str, action: str) -> dict[str, Any]:
        _project_view(app, pid)
        getattr(app.orchestrator, action)(pid)
        if action == "cancel":
            app.queue.cancel_project(pid)
        else:
            schedule(pid)
        return _project_view(app, pid)

    @api.post("/api/projects/{pid}/pause", dependencies=A)
    def pause(pid: str):
        return _control(pid, "pause")

    @api.post("/api/projects/{pid}/resume", dependencies=A)
    def resume(pid: str):
        return _control(pid, "resume")

    @api.post("/api/projects/{pid}/cancel", dependencies=A)
    def cancel(pid: str):
        return _control(pid, "cancel")

    @api.post("/api/projects/{pid}/retry/{phase}", dependencies=A)
    def retry(pid: str, phase: str):
        if phase not in PHASES:
            raise HTTPException(400, "Fase desconocida")
        app.orchestrator.retry_phase(pid, phase)
        schedule(pid)
        return _project_view(app, pid)

    @api.post("/api/projects/{pid}/redo", dependencies=A)
    def redo(pid: str, body: RedoIn):
        if body.from_phase not in PHASES:
            raise HTTPException(400, "Fase desconocida")
        app.orchestrator.redo_scenes(pid, body.scenes, body.from_phase, body.reason)
        schedule(pid)
        return _project_view(app, pid)

    @api.post("/api/projects/{pid}/approve", dependencies=A)
    def approve(pid: str, body: ApproveIn):
        _project_view(app, pid)
        try:
            a = app.orchestrator.approve(pid, body.gate, approved=body.approved, note=body.note)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        schedule(pid)
        return {"approval": a.model_dump(), **_project_view(app, pid)}

    # ------------------------------------------------------------ agentes y sala
    @api.get("/api/agents", dependencies=A)
    def agents() -> dict[str, Any]:
        return {"agents": [a.model_dump() for a in board.snapshot()],
                "links": [link.model_dump() for link in board.links()],
                "pipeline": [{"id": p.id, "number": p.number, "title": p.title, "agent": p.agent, "kind": p.kind}
                             for p in PIPELINE]}

    @api.get("/api/events", dependencies=A)
    def events(limit: int = Query(200, le=2000)) -> list[dict[str, Any]]:
        return app.store.events(limit=limit)

    @api.get("/api/platforms", dependencies=A)
    def platforms() -> list[dict[str, Any]]:
        from ..core.platforms import load_profiles
        return [p.model_dump(mode="json") | {"is_verified": p.is_verified} for p in load_profiles().values()]

    # ------------------------------------------------------------ biblioteca
    @api.get("/api/library", dependencies=A)
    def library() -> dict[str, Any]:
        items = []
        for p in app.store.list_projects():
            ws_root = app.settings.projects_dir / p.id
            assets = _read_json(ws_root / "resources" / "assets.json") or {}
            for scene, a in assets.items():
                rel = None
                try:
                    rel = str(Path(a["path"]).resolve().relative_to(ws_root.resolve()))
                except ValueError:
                    pass
                items.append({"project_id": p.id, "project": p.spec.name, "scene": int(scene), "kind": a["kind"],
                              "provider": a.get("metadata", {}).get("provider_instance") or a["provider"],
                              "license": a.get("license"), "prompt": a.get("prompt"), "width": a.get("width"),
                              "height": a.get("height"), "file": rel})
        return {"assets": items}

    # ------------------------------------------------------------ proveedores
    def _reg():
        if not app.provider_system:
            raise HTTPException(503, "Registro de proveedores no disponible")
        return app.provider_system.registry

    @api.get("/api/providers", dependencies=A)
    def providers():
        reg = _reg()
        return {"providers": [v.model_dump(mode="json") for v in reg.views()],
                "categories": [c.value for c in ProviderCategory]}

    @api.get("/api/providers/catalog", dependencies=A)
    def catalog():
        return [i.model_dump(mode="json") for i in _reg().adapter_catalog()]

    @api.post("/api/providers", dependencies=A, status_code=201)
    def add_provider(body: ProviderIn):
        try:
            cfg = _reg().add(body.adapter, id=body.id, display_name=body.display_name, params=body.params,
                             enabled=body.enabled, monthly_budget_eur=body.monthly_budget_eur,
                             max_generations_per_project=body.max_generations_per_project)
        except RegistryError as e:
            raise HTTPException(400, str(e)) from e
        return cfg.model_dump(mode="json")

    @api.patch("/api/providers/{prov}", dependencies=A)
    def patch_provider(prov: str, body: ProviderPatch):
        try:
            return _reg().update(prov, **body.model_dump(exclude_unset=True)).model_dump(mode="json")
        except RegistryError as e:
            raise HTTPException(400, str(e)) from e

    @api.delete("/api/providers/{prov}", dependencies=A)
    def delete_provider(prov: str):
        try:
            _reg().remove(prov)
        except RegistryError as e:
            raise HTTPException(404, str(e)) from e
        return {"ok": True}

    @api.put("/api/providers/{prov}/credentials", dependencies=A)
    def set_credential(prov: str, body: CredentialIn):
        try:
            return {"key": body.key, "hint": _reg().set_credential(prov, body.key, body.value)}
        except RegistryError as e:
            raise HTTPException(400, str(e)) from e

    @api.delete("/api/providers/{prov}/credentials/{key}", dependencies=A)
    def delete_credential(prov: str, key: str):
        _reg().delete_credential(prov, key)
        return {"ok": True}

    @api.post("/api/providers/{prov}/test", dependencies=A)
    def test_provider(prov: str):
        try:
            return _reg().test(prov).model_dump(mode="json")
        except RegistryError as e:
            raise HTTPException(404, str(e)) from e

    @api.post("/api/providers/order", dependencies=A)
    def order_providers(body: OrderIn):
        try:
            return [p.model_dump(mode="json") for p in _reg().set_order(body.category, body.ids, enable=body.ids[:1])]
        except RegistryError as e:
            raise HTTPException(400, str(e)) from e

    # ------------------------------------------------------------ presupuesto
    @api.get("/api/budget", dependencies=A)
    def budget():
        if not app.provider_system:
            return {"summary": None, "ledger": []}
        b = app.provider_system.budget
        return {"summary": b.summary(), "ledger": b.ledger(), "warn_fraction": b.warn_fraction,
                "spend_authorized_providers": b.get_setting("spend_authorized_providers", [])}

    @api.put("/api/budget", dependencies=A)
    def set_budget(body: BudgetIn):
        if not app.provider_system:
            raise HTTPException(503, "Presupuesto no disponible")
        b = app.provider_system.budget
        for k, v in body.model_dump(exclude_unset=True).items():
            b.set_setting("budget_warn_fraction" if k == "warn_fraction" else k, v)
        return budget()

    # ------------------------------------------------------------ modelos Claude y cola
    @api.get("/api/models", dependencies=A)
    def models():
        usage = app.store.llm_usage()
        by_agent: dict[str, dict[str, Any]] = {}
        for u in usage:
            d = by_agent.setdefault(u["agent"], {"calls": 0, "seconds": 0.0, "models": {}})
            d["calls"] += 1
            d["seconds"] = round(d["seconds"] + (u.get("duration_s") or 0), 2)
            m = u.get("model_served") or "?"
            d["models"][m] = d["models"].get(m, 0) + 1
        return {"config": app.models.model_dump(), "aliases": ["sonnet", "opus", "haiku"],
                "usage_by_agent": by_agent, "llm_provider": app.llm.name,
                "lanes": {k: v.model_dump() for k, v in app.queue.lanes().items()},
                "note": "El consumo de Claude Pro no se factura por uso; estas cifras son indicativas."}

    @api.put("/api/models", dependencies=A)
    def set_models(body: ModelsIn):
        values = [v for v in [body.default, body.fallback, *body.agents.values()] if v]
        bad = [v for v in values if not MODEL_RE.match(v)]
        unknown = set(body.agents) - set(board.agents)
        if bad or unknown:
            raise HTTPException(400, f"Modelos inválidos {bad} o agentes desconocidos {sorted(unknown)}")
        overrides = body.model_dump(exclude_unset=True)
        if app.provider_system:
            prev = app.provider_system.budget.get_setting("model_overrides", {}) or {}
            merged = {**prev, **{k: v for k, v in overrides.items() if k != "agents"},
                      "agents": {**prev.get("agents", {}), **overrides.get("agents", {})}}
            app.provider_system.budget.set_setting("model_overrides", merged)
        app.models.apply_overrides(overrides)
        return models()

    @api.get("/api/queue", dependencies=A)
    def queue_state():
        return {"lanes": {k: v.model_dump() for k, v in app.queue.lanes().items()}, "stats": app.queue.stats(),
                "active": [t.model_dump() for t in app.queue.tasks(status="leased")] +
                          [t.model_dump() for t in app.queue.tasks(status="queued")]}

    @api.put("/api/queue/concurrency", dependencies=A)
    def set_concurrency(body: ConcurrencyIn):
        n = app.queue.set_concurrency(body.lane, body.concurrency)
        return {"lane": body.lane, "concurrency": n, "note": "Se aplica en el próximo reinicio del worker"}

    @api.post("/api/queue/claude/resume", dependencies=A)
    def resume_claude():
        app.worker.resume_claude()
        return queue_state()

    # ------------------------------------------------------------ WebSocket
    @api.websocket("/ws")
    async def ws(websocket: WebSocket):
        if token and websocket.query_params.get("token") != token:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        entry = (q, asyncio.get_running_loop())
        with clients_lock:
            clients.add(entry)
        async def pump() -> None:
            while True:
                msg = await q.get()
                await websocket.send_json({"type": "event", **msg})

        sender: asyncio.Task | None = None
        try:
            await websocket.send_json({"type": "hello", "agents": [a.model_dump() for a in board.snapshot()]})
            sender = asyncio.create_task(pump())
            # Se escucha al cliente para detectar la desconexión (si no, la conexión quedaría
            # colgada y bloquearía el apagado ordenado del servidor).
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if sender:
                sender.cancel()
            with clients_lock:
                clients.discard(entry)

    @api.exception_handler(KeyError)
    async def _not_found(_: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={"detail": f"No encontrado: {exc}"})

    # ------------------------------------------------------------ interfaz compilada
    if FRONTEND_DIST.exists():
        api.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return api


def main() -> None:  # pragma: no cover - punto de entrada
    import argparse

    import uvicorn

    from ..app import build_app
    from ..core.logging_setup import setup_logging
    from ..core.settings import Settings

    ap = argparse.ArgumentParser(description="Servidor de la sala de producción")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--offline", action="store_true", help="Sin Claude (borradores locales)")
    ap.add_argument("--no-worker", action="store_true")
    args = ap.parse_args()
    settings = Settings.from_env()
    if args.offline:
        settings.llm_provider = "local_draft"
    setup_logging(settings.logs_dir)
    app = build_app(settings)
    if args.host not in ("127.0.0.1", "localhost") and not os.environ.get("YTAUTO_API_TOKEN"):
        raise SystemExit("Para escuchar fuera de localhost define YTAUTO_API_TOKEN")
    uvicorn.run(create_api(app, start_worker=not args.no_worker), host=args.host, port=args.port,
                timeout_graceful_shutdown=10)


if __name__ == "__main__":  # pragma: no cover
    main()
