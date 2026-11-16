"""Producción completa de prueba con proveedores 100 % locales y gratuitos.

Uso:  python scripts/demo_production.py [--claude] [--topic "..."] [--duration 60]
Sin --claude usa borradores locales (no consume la suscripción). Con --claude usa Claude Code.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from ytauto.app import build_app  # noqa: E402
from ytauto.core.models import ProjectSpec  # noqa: E402
from ytauto.core.settings import Settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude", action="store_true", help="Usar Claude Code (consume la suscripción)")
    ap.add_argument("--topic", default="los secretos de los pulpos")
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--data-dir", default=None, help="Directorio de datos (por defecto, temporal)")
    args = ap.parse_args()
    data = Path(args.data_dir or tempfile.mkdtemp(prefix="ytauto_demo_"))
    settings = Settings.from_env(load_env_file=False)
    settings.data_dir, settings.projects_dir = data / "data", data / "projects"
    settings.db_path, settings.logs_dir = data / "data" / "ytauto.db", data / "data" / "logs"
    settings.backups_dir = data / "backups"
    settings.llm_provider = "claude_cli" if args.claude else "local_draft"
    app = build_app(settings)
    print("Proveedores:", [(v.category.value, v.id, v.role) for v in app.provider_system.registry.views()])
    spec = ProjectSpec(name="Demo local", topic=args.topic, duration_s=args.duration, require_script_approval=False,
                       intensity="high")
    pid = app.orchestrator.create_project(spec)
    t0 = time.time()
    for gate, note in (("final_approval", "demo"), ("publish_decision", "publicación manual")):
        app.worker.schedule(pid)
        app.worker.run_until_idle()
        waiting = app.orchestrator.next_phase(pid)
        if waiting is None or waiting.id not in (gate, "publish"):
            break  # error o bloqueo: se informa abajo
        app.orchestrator.approve(pid, gate, note=note)
    app.worker.schedule(pid)
    app.worker.run_until_idle()
    for ph in app.store.list_phases(pid):
        print(f"{ph.phase:22s} {ph.status.value:10s} {ph.summary or ph.error or ''}"[:160])
    root = settings.projects_dir / pid
    print("\nTiempo total: %.1fs" % (time.time() - t0))
    print("Proyecto:", root)
    exports = root / "exports" / "exports.json"
    if exports.exists():
        print(json.dumps(json.loads(exports.read_text()), indent=2, ensure_ascii=False))
    return 0 if app.store.get_project(pid).status.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
