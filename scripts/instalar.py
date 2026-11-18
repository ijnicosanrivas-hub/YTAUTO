"""Instalador de YTAUTO (Windows, macOS y Linux).

Crea el entorno virtual, instala las dependencias, compila la interfaz, prepara `.env` y ejecuta el diagnóstico.
En Windows lo llama INSTALAR_WINDOWS.bat tras instalar Python, Git, FFmpeg, la voz y Claude Code.

Uso:  python scripts/instalar.py [--skip-ui] [--no-claude] [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)


def venv_python(root: Path = ROOT, platform: str = sys.platform) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if platform.startswith("win") else "bin/python")


def plan(root: Path = ROOT, platform: str = sys.platform, skip_ui: bool = False, npm: str | None = None,
         no_claude: bool = False, ui_built: bool = False) -> list[tuple[str, list[str], Path | None]]:
    """Pasos (descripción, orden, carpeta de trabajo). Función pura: se puede comprobar sin ejecutar nada."""
    py = str(venv_python(root, platform))
    steps: list[tuple[str, list[str], Path | None]] = [
        ("Crear el entorno de Python (.venv)", [sys.executable, "-m", "venv", str(root / ".venv")], None),
        ("Instalar las dependencias de Python", [py, "-m", "pip", "install", "--disable-pip-version-check", "-e", "."], root),
    ]
    if not skip_ui and not ui_built and npm:
        steps += [("Instalar las dependencias de la interfaz", [npm, "install", "--no-audit", "--no-fund"], root / "frontend"),
                  ("Compilar la interfaz", [npm, "run", "build"], root / "frontend")]
    doctor = [py, "-m", "ytauto", "doctor"] + (["--no-claude"] if no_claude else [])
    steps.append(("Comprobar la instalacion", doctor, root))
    return steps


def ensure_env(root: Path = ROOT) -> bool:
    """Crea .env a partir de la plantilla si no existe. Devuelve True si lo creó."""
    env, example = root / ".env", root / ".env.example"
    if env.exists() or not example.exists():
        return False
    shutil.copyfile(example, env)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Instala YTAUTO")
    ap.add_argument("--skip-ui", action="store_true", help="No compilar la interfaz")
    ap.add_argument("--no-claude", action="store_true", help="No exigir Claude Code en el diagnostico")
    ap.add_argument("--dry-run", action="store_true", help="Solo muestra lo que haria")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    if sys.version_info < MIN_PYTHON:
        print(f"Se necesita Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior (tienes {sys.version.split()[0]}).")
        return 1
    ui_built = (ROOT / "frontend" / "dist" / "index.html").is_file()  # el paquete ya incluye la interfaz compilada
    npm = shutil.which("npm")
    if not ui_built and npm is None and not args.skip_ui:
        print("AVISO: la interfaz no esta compilada y no se encuentra Node.js (npm). Descarga el programa completo de nuevo.")
    steps = plan(skip_ui=args.skip_ui, npm=npm, no_claude=args.no_claude, ui_built=ui_built)
    venv_exists = (ROOT / ".venv").exists()
    for i, (title, cmd, cwd) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {title}")
        if i == 1 and venv_exists:
            print("    (ya existe: se reutiliza)")
            continue
        print("    >", " ".join(cmd))
        if args.dry_run:
            continue
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            if title.startswith("Comprobar"):
                print("\nLa instalacion termino, pero faltan cosas (lee los avisos de arriba).")
                return 0
            print(f"\nERROR en el paso: {title} (codigo {result.returncode})")
            return result.returncode
    if not args.dry_run and ensure_env():
        print("\nSe ha creado el archivo de configuracion .env (puedes dejarlo como esta).")
    print("\nListo. Para usar YTAUTO, abre INICIAR_WINDOWS.bat (Windows) o ejecuta: python -m ytauto.api.server")
    return 0


if __name__ == "__main__":
    sys.exit(main())
