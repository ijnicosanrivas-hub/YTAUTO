"""Línea de comandos: `python -m ytauto <orden>`.

También la usa el modo interactivo de Claude Code para consultar y controlar producciones.
"""
from __future__ import annotations

import argparse
import json
import sys

from .core.models import Platform, ProjectSpec
from .core.settings import REPO_ROOT, Settings


def _providers(args):
    if getattr(args, "mock_providers", False):
        from .providers import mock as m
        from .providers.gateway import DirectGateway
        from .providers.interfaces import ProviderCategory as C
        from .providers.subtitle.proportional import ProportionalSubtitleProvider
        return DirectGateway({C.IMAGE: m.MockImageProvider(), C.TTS: m.MockTTSProvider(),
                              C.MUSIC: m.MockMusicProvider(), C.SFX: m.MockSFXProvider(),
                              C.SUBTITLE: ProportionalSubtitleProvider(), C.RENDERING: m.MockRenderingProvider(),
                              C.PUBLISHING: m.MockPublishingProvider()})
    return None  # Provider Registry persistido (fase 4)


def _app(args):
    from .app import build_app
    from .core.logging_setup import setup_logging
    settings = Settings.from_env()
    if getattr(args, "offline", False):
        settings.llm_provider = "local_draft"
    setup_logging(settings.logs_dir)
    return build_app(settings, providers=_providers(args))


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ytauto", description="Fábrica multiagente de vídeos cortos")
    p.add_argument("--offline", action="store_true", help="Sin Claude: borradores locales (pruebas)")
    p.add_argument("--mock-providers", action="store_true", help="Proveedores simulados (pruebas)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="Crear proyecto")
    n.add_argument("--name", required=True)
    n.add_argument("--topic", required=True)
    n.add_argument("--idea", default="")
    n.add_argument("--duration", type=int, default=60)
    n.add_argument("--language", default="es")
    n.add_argument("--style")
    n.add_argument("--intensity", choices=["low", "medium", "high"], default="medium")
    n.add_argument("--platforms", default="youtube_shorts,instagram_reels,tiktok")
    n.add_argument("--auto", action="store_true", help="Sin aprobación manual del guion")

    dc = sub.add_parser("doctor", help="Diagnostica la instalación y explica cómo arreglar lo que falte")
    dc.add_argument("--no-claude", action="store_true", help="No exigir Claude Code (modo sin Claude)")
    sub.add_parser("list", help="Listar proyectos")
    st = sub.add_parser("status", help="Estado de un proyecto")
    st.add_argument("project_id")
    r = sub.add_parser("run", help="Ejecutar el worker")
    r.add_argument("--forever", action="store_true")
    ap = sub.add_parser("approve", help="Aprobar/rechazar una puerta")
    ap.add_argument("project_id")
    ap.add_argument("gate", help="script_approval | final_approval | publish:<plataforma> | publish_decision")
    ap.add_argument("--reject", action="store_true")
    ap.add_argument("--note", default="")
    for name in ("pause", "resume", "cancel"):
        sub.add_parser(name).add_argument("project_id")
    rd = sub.add_parser("redo", help="Rehacer escenas concretas")
    rd.add_argument("project_id")
    rd.add_argument("--scenes", required=True, help="Índices separados por comas")
    rd.add_argument("--from-phase", default="resource_generation")
    sub.add_parser("resume-claude", help="Reanudar el carril de Claude tras límite o login")
    sub.add_parser("queue", help="Estado de la cola")
    pv = sub.add_parser("providers", help="Configuración de proveedores")
    pvs = pv.add_subparsers(dest="pcmd", required=True)
    pvs.add_parser("list")
    pvs.add_parser("catalog", help="Adaptadores instalados")
    pa = pvs.add_parser("add")
    pa.add_argument("adapter")
    pa.add_argument("--id")
    pa.add_argument("--params", default="{}", help="JSON de parámetros")
    pa.add_argument("--monthly-budget", type=float)
    pk = pvs.add_parser("set-key", help="Guardar una credencial (se pide de forma oculta)")
    pk.add_argument("provider_id")
    pk.add_argument("--key", default="api_key")
    for name in ("enable", "disable", "remove", "test"):
        pvs.add_parser(name).add_argument("provider_id")
    pp = pvs.add_parser("primary")
    pp.add_argument("category")
    pp.add_argument("provider_id")
    pf = pvs.add_parser("fallbacks")
    pf.add_argument("category")
    pf.add_argument("provider_ids", help="Ids separados por comas")
    bg = sub.add_parser("budget", help="Presupuestos y consumo externo")
    bg.add_argument("--monthly", type=float, help="Fijar presupuesto mensual global (€)")
    sp = sub.add_parser("authorize-spend", help="Autorizar gasto de un proveedor de pago en un proyecto")
    sp.add_argument("project_id")
    sp.add_argument("provider_id")
    b = sub.add_parser("backup", help="Copia de seguridad")
    b.add_argument("--include-media", action="store_true")

    args = p.parse_args(argv)
    from .core.settings import force_utf8_console
    force_utf8_console()
    if args.cmd == "doctor":  # no necesita base de datos ni aplicación
        from .doctor import doctor
        return doctor(offline=args.no_claude or args.offline)
    app = _app(args)
    orch, worker = app.orchestrator, app.worker

    if args.cmd == "new":
        spec = ProjectSpec(name=args.name, topic=args.topic, idea=args.idea, duration_s=args.duration,
                           language=args.language, visual_style=args.style, intensity=args.intensity,
                           platforms=[Platform(x) for x in args.platforms.split(",")],
                           require_script_approval=not args.auto, mode="auto" if args.auto else "custom")
        pid = orch.create_project(spec)
        worker.schedule(pid)
        _print({"project_id": pid})
    elif args.cmd == "list":
        _print([{"id": x.id, "name": x.spec.name, "status": x.status.value} for x in app.store.list_projects()])
    elif args.cmd == "status":
        proj = app.store.get_project(args.project_id)
        _print({"project": proj.model_dump(mode="json", exclude={"spec"}),
                "phases": [{"phase": ph.phase, "status": ph.status.value, "attempts": ph.attempts,
                            "summary": ph.summary, "error": ph.error} for ph in app.store.list_phases(args.project_id)]})
    elif args.cmd == "run":
        worker.recover_on_startup()
        if args.forever:
            try:
                worker.run_forever()
            except KeyboardInterrupt:
                worker.stop()
        else:
            _print({"tasks_executed": worker.run_until_idle(), "lanes": {k: v.model_dump() for k, v in app.queue.lanes().items()}})
    elif args.cmd == "approve":
        a = orch.approve(args.project_id, args.gate, approved=not args.reject, note=args.note)
        worker.schedule(args.project_id)
        _print(a.model_dump())
    elif args.cmd in ("pause", "resume", "cancel"):
        getattr(orch, args.cmd)(args.project_id)
        if args.cmd == "cancel":
            app.queue.cancel_project(args.project_id)
        if args.cmd == "resume":
            worker.schedule(args.project_id)
        _print({"ok": True})
    elif args.cmd == "redo":
        orch.redo_scenes(args.project_id, [int(x) for x in args.scenes.split(",")], args.from_phase)
        worker.schedule(args.project_id)
        _print({"ok": True})
    elif args.cmd == "resume-claude":
        worker.resume_claude()
        _print({"ok": True})
    elif args.cmd == "queue":
        _print({"lanes": {k: v.model_dump() for k, v in app.queue.lanes().items()}, "stats": app.queue.stats()})
    elif args.cmd == "providers":
        _providers_cmd(app, args)
    elif args.cmd == "budget":
        ps = _require_registry(app)
        if args.monthly is not None:
            ps.budget.set_setting("monthly_budget_eur", args.monthly)
        _print(ps.budget.summary())
    elif args.cmd == "authorize-spend":
        a = orch.approve(args.project_id, f"spend:{args.provider_id}")
        worker.schedule(args.project_id)
        _print(a.model_dump())
    elif args.cmd == "backup":
        from .db.backup import backup
        out = backup(app.settings.db_path, app.settings.backups_dir, REPO_ROOT / "config", app.settings.projects_dir,
                     include_media=args.include_media)
        _print({"backup": str(out)})
    return 0


def _require_registry(app):
    if app.provider_system is None:
        raise SystemExit("Esta orden requiere el registro de proveedores (no uses --mock-providers)")
    return app.provider_system


def _providers_cmd(app, args) -> None:
    import getpass
    reg = _require_registry(app).registry
    c = args.pcmd
    if c == "list":
        _print([v.model_dump(mode="json", include={"id", "adapter", "category", "role", "enabled", "is_paid",
                                                   "credentials", "missing_credentials", "status"})
                for v in reg.views()])
    elif c == "catalog":
        _print([i.model_dump(mode="json") for i in reg.adapter_catalog()])
    elif c == "add":
        _print(reg.add(args.adapter, id=args.id, params=json.loads(args.params),
                       monthly_budget_eur=args.monthly_budget).model_dump(mode="json"))
    elif c == "set-key":
        value = getpass.getpass(f"{args.key} para {args.provider_id} (no se mostrará): ")
        _print({"saved": reg.set_credential(args.provider_id, args.key, value)})
    elif c in ("enable", "disable", "remove"):
        getattr(reg, c)(args.provider_id)
        _print({"ok": True})
    elif c == "test":
        _print(reg.test(args.provider_id).model_dump(mode="json"))
    elif c == "primary":
        _print([p.id for p in reg.set_primary(args.category, args.provider_id)])
    elif c == "fallbacks":
        _print([p.id for p in reg.set_fallbacks(args.category, args.provider_ids.split(","))])


if __name__ == "__main__":
    sys.exit(main())
