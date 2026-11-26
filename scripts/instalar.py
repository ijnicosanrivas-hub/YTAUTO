"""Instalador y actualizador de YTAUTO (Windows, macOS y Linux).

Lo llaman INSTALAR_WINDOWS.bat, INSTALAR_MAC.command e instalar.sh después de asegurar Python, FFmpeg, la voz y
Claude Code (cada herramienta se busca antes de instalarla: si ya está, no se toca).

Dos casos, decididos solos:
- **Equipo nuevo**: instala el paquete completo donde se ha descomprimido (entorno de Python, dependencias, interfaz,
  `.env`, accesos directos) y lo apunta en el registro del usuario.
- **Ya hay una instalación** (apuntada en el registro o, en versiones antiguas, encontrada por su acceso directo):
  la ACTUALIZA en su sitio. Compara archivo a archivo (SHA-256) y copia solo lo nuevo o cambiado, borra lo que la
  versión nueva ya no trae (solo si nadie lo modificó), y reinstala dependencias solo si `pyproject.toml` cambió o el
  entorno no funciona. Los datos del usuario NO se tocan nunca: `data/` (claves cifradas, licencias, base de datos),
  `library/`, `projects/`, `backups/`, `tools/` (FFmpeg, voz, Higgsfield), `.venv/` y `.env`.
  Si un archivo de la aplicación fue modificado a mano, se guarda una copia en `backups/actualizacion-<fecha>/`.

Uso:  python scripts/instalar.py [--destino CARPETA | --aqui] [--skip-ui] [--no-claude] [--dry-run]
      python scripts/instalar.py --resolver-destino   (imprime dónde está/irá la instalación; lo usa el .bat)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
APP_PORT = 8000
APP_OPEN = 75  # código de salida «la aplicación está abierta: ciérrala y repite» (los lanzadores lo reconocen)
# Nunca se copian, se comparan ni se borran: son del usuario o se generan en su equipo.
PROTECTED = {"data", "library", "projects", "backups", "tools", "logs", ".venv", "venv", ".git", "paquetes",
             "node_modules", ".env", ".pytest_cache", ".ruff_cache", "htmlcov", "demo_output"}
SKIP_PARTS = {"__pycache__", "node_modules", "dist-demo", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm"}
STATE_FILE = ".ytauto-instalado.json"  # manifiesto de lo instalado (para saber qué borrar en la próxima versión)
PACKAGE_MANIFEST = ".ytauto-paquete.json"  # lista de archivos que trae el paquete (la escribe scripts/empaquetar.py)
DEPS_STAMP = ".ytauto-deps"            # dentro de .venv: huella de las dependencias instaladas


# ------------------------------------------------------------------ utilidades
def venv_python(root: Path = ROOT, platform: str = sys.platform) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if platform.startswith("win") else "bin/python")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def version_of(root: Path, use_git: bool = True) -> str:
    v = root / "VERSION.txt"
    if v.is_file():
        return v.read_text(encoding="utf-8", errors="replace").strip() or "desconocida"
    if not use_git:
        return "desconocida"
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "desconocida"


def is_install(root: Path | None) -> bool:
    return bool(root) and (root / "pyproject.toml").is_file() and (root / "backend" / "ytauto").is_dir()


# ------------------------------------------------------------------ dónde está la instalación
def registry_path(platform: str = sys.platform, env: dict[str, str] | None = None, home: Path | None = None) -> Path:
    """Registro por usuario con la carpeta de la instalación (fuera de la carpeta del programa)."""
    env = dict(os.environ) if env is None else env
    home = home or Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if platform.startswith("win"):
        base = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return base / "YTAUTO" / "instalacion.json"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "YTAUTO" / "instalacion.json"
    return Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "ytauto" / "instalacion.json"


def desktop_dirs(platform: str = sys.platform, env: dict[str, str] | None = None, home: Path | None = None) -> list[Path]:
    env = dict(os.environ) if env is None else env
    home = home or Path(env.get("USERPROFILE") or env.get("HOME") or Path.home())
    # Windows en español con OneDrive guarda el Escritorio como «OneDrive\\Escritorio».
    cands = [home / "Desktop", home / "Escritorio"]
    if platform.startswith("win"):
        cands += [home / "OneDrive" / "Desktop", home / "OneDrive" / "Escritorio"]
        cands += [Path(v) / sub for k, v in env.items() if k.upper().startswith("ONEDRIVE") and v
                  for sub in ("Desktop", "Escritorio")]
    seen: list[Path] = []
    for d in cands:
        if d.is_dir() and d not in seen:
            seen.append(d)
    return seen


def read_text_any(path: Path) -> str:
    """Accesos de cmd escritos con la página de códigos de la consola (OEM): rutas con tildes o «ñ»."""
    raw = path.read_bytes()
    for enc in ("utf-8", "oem", "cp850", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _root_from_launcher(launcher: Path) -> Path | None:
    for cand in (launcher.parent, launcher.parent.parent.parent):
        if is_install(cand):
            return cand
    return None


def legacy_roots(platform: str = sys.platform, env: dict[str, str] | None = None, home: Path | None = None) -> list[Path]:
    """Instalaciones anteriores a este actualizador: se encuentran por el acceso directo que crearon."""
    env = dict(os.environ) if env is None else env
    home = home or Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    found: list[Path] = []
    files: list[Path] = []
    for d in desktop_dirs(platform, env, home):
        files += [d / "YTAUTO.bat", d / "YTAUTO.command"]
    files.append(home / ".local" / "share" / "applications" / "ytauto.desktop")
    for f in files:
        if not f.is_file():
            continue
        text = read_text_any(f)
        for m in re.finditer(r'"([^"]+?(?:INICIAR_WINDOWS\.bat|INICIAR_MAC\.command|iniciar\.sh))"', text):
            root = _root_from_launcher(Path(m.group(1)))
            if root and root not in found:
                found.append(root)
    return found


SEARCH_DIRS = ("Desktop", "Escritorio", "Downloads", "Descargas", "Documents", "Documentos", "OneDrive")
SKIP_DIRS = {"node_modules", ".venv", "venv", ".git", "AppData", "Library", "__pycache__", "site-packages",
             "projects", "library", "data", "tools", "backups"}


def find_installs(home: Path, env: dict[str, str] | None = None, max_depth: int = 4,
                  limit_dirs: int = 20000) -> list[Path]:
    """Instalaciones de YTAUTO en las carpetas habituales (por si no hay acceso directo ni registro)."""
    env = dict(os.environ) if env is None else env
    roots = [home / d for d in SEARCH_DIRS] + [home, Path(env.get("SystemDrive", "C:") + "\\") / "YTAUTO"]
    found: list[Path] = []
    seen = 0
    for base in roots:
        if not base.is_dir():
            continue
        depth0 = len(base.parts)
        for dirpath, dirnames, filenames in os.walk(base):
            seen += 1
            if seen > limit_dirs:
                return found
            here = Path(dirpath)
            if "pyproject.toml" in filenames and is_install(here):
                if here not in found:
                    found.append(here)
                dirnames[:] = []  # dentro de una instalación no hay otras
                continue
            if len(here.parts) - depth0 >= max_depth or (base == home and here != home):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
    return found


def user_data_size(root: Path) -> int:
    """Cuánto «vivido» tiene una instalación: tamaño de su base de datos (licencias, cuentas, proyectos)."""
    data = root / "data"
    if not data.is_dir():
        return 0
    size = sum(f.stat().st_size for f in data.glob("*.db") if f.is_file())
    if (data / "secrets" / "master.key").is_file():
        size += 1
    return size


def read_registry(reg: Path) -> dict:
    try:
        return json.loads(reg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def resolve_destination(source: Path, reg: Path, legacy: list[Path], explicit: Path | None = None,
                        here: bool = False, found: list[Path] | None = None) -> tuple[Path, str]:
    """(carpeta de la instalación, motivo). Motivos: explicita · aqui · registrada · anterior · encontrada · nueva.

    Si hay varias instalaciones, gana la que tiene TUS datos (la base de datos más grande): así una carpeta nueva
    descomprimida, o una instalación «nueva» creada por error, nunca deja huérfanas tus licencias y proyectos."""
    if explicit:
        return explicit.resolve(), "explicita"
    if here:
        return source, "aqui"
    registered = read_registry(reg).get("root")
    reg_root = Path(registered) if registered and is_install(Path(registered)) else None
    ordered: list[tuple[Path, str]] = []
    for cand, why in ([(reg_root, "registrada")] if reg_root else []) + [(c, "anterior") for c in legacy] + \
            [(c, "encontrada") for c in (found or [])] + [(source, "nueva")]:
        if is_install(cand) and all(cand.resolve() != o.resolve() for o, _ in ordered):
            ordered.append((cand, why))
    sizes = {c: user_data_size(c) for c, _ in ordered}
    best = max(sizes.values(), default=0)
    if best > 0:
        # La que tiene más datos; a igualdad, el orden de preferencia (registrada, acceso directo, encontrada).
        return next((c, w) for c, w in ordered if sizes[c] == best)
    return ordered[0] if ordered else (source, "nueva")


# ------------------------------------------------------------------ comparación y copia de archivos
def app_files(root: Path) -> dict[str, str]:
    """Archivos de la aplicación (ruta relativa con «/» → SHA-256), sin datos ni artefactos locales."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in PROTECTED]
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        for name in filenames:
            rel = (rel_dir / name).as_posix()
            if rel_dir == Path(".") and (name in PROTECTED or name == STATE_FILE or name.startswith(".ytauto-")):
                continue
            if Path(name).suffix in SKIP_SUFFIXES:
                continue
            out[rel] = sha256(Path(dirpath) / name)
    return out


def program_files(root: Path, use_git: bool = True) -> dict[str, str]:
    """Archivos que son «el programa» en esa carpeta: los del manifiesto del paquete, los versionados en git o, en
    último caso, todos menos los datos. Lo que el usuario añada por su cuenta nunca cuenta (ni se borra)."""
    man = root / PACKAGE_MANIFEST
    if man.is_file():
        try:
            listed = json.loads(man.read_text(encoding="utf-8")).get("files", {})
            return {rel: sha256(root / rel) for rel in listed if (root / rel).is_file() and not _protected(rel)}
        except (OSError, ValueError):
            pass
    if use_git and (root / ".git").exists():
        try:
            out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, timeout=60)
            if out.returncode == 0:
                rels = [r for r in out.stdout.decode("utf-8", "replace").split("\0") if r]
                return {r: sha256(root / r) for r in rels if (root / r).is_file() and not _protected(r)}
        except (OSError, subprocess.SubprocessError):
            pass
    return app_files(root)


def _protected(rel: str) -> bool:
    first = rel.split("/", 1)[0]
    return first in PROTECTED or first == STATE_FILE or first.startswith(".ytauto-")


def hashes_of(root: Path, rels) -> dict[str, str]:
    return {r: sha256(root / r) for r in rels if (root / r).is_file()}


def sync_plan(src_files: dict[str, str], dst_files: dict[str, str], previous: dict[str, str]) -> dict[str, list[str]]:
    """Qué hacer en la carpeta instalada. Función pura.

    - add / update: archivos nuevos o distintos en la versión nueva.
    - backup: de esos, los que el usuario cambió a mano (difieren de lo que instaló la versión anterior).
    - remove: los que la versión anterior instaló y la nueva ya no trae, si siguen intactos.
    - keep_modified: los que la nueva ya no trae pero el usuario modificó (se dejan).
    """
    plan: dict[str, list[str]] = {"add": [], "update": [], "backup": [], "remove": [], "keep_modified": [], "same": []}
    for rel, h in sorted(src_files.items()):
        if _protected(rel):
            continue
        cur = dst_files.get(rel)
        if cur is None:
            plan["add"].append(rel)
        elif cur == h:
            plan["same"].append(rel)
        else:
            plan["update"].append(rel)
            if rel in previous and previous[rel] != cur:
                plan["backup"].append(rel)
    for rel, old in sorted(previous.items()):
        if rel in src_files or rel not in dst_files or _protected(rel):
            continue
        (plan["remove"] if dst_files[rel] == old else plan["keep_modified"]).append(rel)
    return plan


def apply_sync(src: Path, dst: Path, plan: dict[str, list[str]], stamp: str | None = None) -> Path | None:
    """Aplica el plan. Devuelve la carpeta de copias de seguridad si hizo falta alguna."""
    backup_dir = None
    if plan["backup"]:
        backup_dir = dst / "backups" / f"actualizacion-{stamp or dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        for rel in plan["backup"]:
            target = backup_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst / rel, target)
    for rel in plan["add"] + plan["update"]:
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".ytauto-nuevo")
        shutil.copy2(src / rel, tmp)
        os.replace(tmp, target)  # cambio atómico: nunca queda un archivo a medias
    for rel in plan["remove"]:
        (dst / rel).unlink(missing_ok=True)
        parent = (dst / rel).parent
        while parent != dst and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return backup_dir


def save_state(dst: Path, files: dict[str, str], version: str) -> None:
    (dst / STATE_FILE).write_text(json.dumps({"version": version, "files": files}, indent=0), encoding="utf-8")


def load_state(dst: Path) -> dict:
    try:
        return json.loads((dst / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ dependencias
def deps_fingerprint(root: Path) -> str:
    data = (root / "pyproject.toml").read_bytes() if (root / "pyproject.toml").is_file() else b""
    return hashlib.sha256(data + f"|py{sys.version_info[0]}.{sys.version_info[1]}".encode()).hexdigest()


def venv_works(root: Path, platform: str = sys.platform) -> bool:
    py = venv_python(root, platform)
    if not py.is_file():
        return False
    try:
        return subprocess.run([str(py), "-c", "import ytauto"], cwd=root, capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def deps_current(root: Path) -> bool:
    stamp = root / ".venv" / DEPS_STAMP
    try:
        return stamp.read_text(encoding="utf-8").strip() == deps_fingerprint(root)
    except OSError:
        return False


def plan(root: Path = ROOT, platform: str = sys.platform, skip_ui: bool = False, npm: str | None = None,
         no_claude: bool = False, ui_built: bool = False, venv_ok: bool = False,
         deps_ok: bool = False) -> list[tuple[str, list[str], Path | None]]:
    """Pasos (descripción, orden, carpeta de trabajo). Función pura: se puede comprobar sin ejecutar nada.

    `venv_ok`: el entorno existe y funciona (no se recrea). `deps_ok`: además, sus dependencias corresponden a este
    `pyproject.toml` (no se reinstalan)."""
    py = str(venv_python(root, platform))
    steps: list[tuple[str, list[str], Path | None]] = []
    if not venv_ok:
        steps.append(("Crear el entorno de Python (.venv)", [sys.executable, "-m", "venv", "--clear", str(root / ".venv")], None))
    if not (venv_ok and deps_ok):
        steps.append(("Instalar las dependencias de Python",
                      [py, "-m", "pip", "install", "--disable-pip-version-check", "-e", "."], root))
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


# ------------------------------------------------------------------ accesos directos y registro
def launcher(root: Path, platform: str = sys.platform) -> Path:
    name, sub = (("INICIAR_WINDOWS.bat", "windows") if platform.startswith("win") else
                 ("INICIAR_MAC.command", "mac") if platform == "darwin" else ("iniciar.sh", "linux"))
    direct = root / name
    return direct if direct.is_file() else root / "instaladores" / sub / name


def write_shortcuts(root: Path, platform: str = sys.platform, env: dict[str, str] | None = None,
                    home: Path | None = None) -> list[Path]:
    """Acceso en el Escritorio (Windows/Mac) o en el menú de aplicaciones (Linux) que abre ESTA instalación."""
    target = launcher(root, platform)
    made: list[Path] = []
    if platform.startswith("win"):
        for d in desktop_dirs(platform, env, home):
            p = d / "YTAUTO.bat"
            # cmd.exe lee los .bat con la página de códigos de la consola (OEM): así una ruta con «ñ» funciona
            p.write_bytes(f'@start "" "{target}"\r\n'.encode("oem" if sys.platform.startswith("win") else "utf-8",
                                                               errors="replace"))
            made.append(p)
    elif platform == "darwin":
        for d in desktop_dirs(platform, env, home):
            p = d / "YTAUTO.command"
            p.write_text(f'#!/bin/bash\nexec "{target}"\n', encoding="utf-8")
            p.chmod(0o755)
            made.append(p)
    else:
        home = home or Path((env or os.environ).get("HOME") or Path.home())
        apps = home / ".local" / "share" / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        p = apps / "ytauto.desktop"
        p.write_text("[Desktop Entry]\nType=Application\nName=YTAUTO\nComment=Fabrica de videos cortos\n"
                     f'Exec=bash "{target}"\nIcon={root / "frontend" / "public" / "icono-512.png"}\nTerminal=true\n'
                     "Categories=AudioVideo;\n", encoding="utf-8")
        made.append(p)
    return made


def write_registry(reg: Path, root: Path, version: str) -> None:
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"root": str(root), "version": version,
                               "updated_at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")


def app_running(port: int = APP_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


# ------------------------------------------------------------------ programa
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Instala o actualiza YTAUTO")
    ap.add_argument("--skip-ui", action="store_true", help="No compilar la interfaz")
    ap.add_argument("--no-claude", action="store_true", help="No exigir Claude Code en el diagnostico")
    ap.add_argument("--dry-run", action="store_true", help="Solo muestra lo que haria")
    ap.add_argument("--destino", type=Path, help="Carpeta de la instalacion (por defecto: la ya instalada o esta)")
    ap.add_argument("--aqui", action="store_true", help="Instalar en esta carpeta aunque haya otra instalacion")
    ap.add_argument("--resolver-destino", action="store_true", help="Imprime la carpeta de la instalacion y sale")
    ap.add_argument("--no-accesos", action="store_true", help="No crear accesos directos")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    reg = registry_path()
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
    dest, why = resolve_destination(ROOT, reg, legacy_roots(), args.destino, args.aqui,
                                    found=[] if (args.destino or args.aqui) else find_installs(home))
    if args.resolver_destino:
        if sys.platform.startswith("win"):
            # cmd lee el resultado con «set /p» en la página de códigos de la consola: rutas con tildes intactas.
            sys.stdout.flush()
            sys.stdout.buffer.write((str(dest) + "\r\n").encode("oem", errors="replace"))
        else:
            print(dest)
        return 0
    if sys.version_info < MIN_PYTHON:
        print(f"Se necesita Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior (tienes {sys.version.split()[0]}).")
        return 1

    new_version = version_of(ROOT, use_git=not args.dry_run)
    updating = dest.resolve() != ROOT.resolve()
    if updating:
        old = load_state(dest).get("version") or version_of(dest, use_git=not args.dry_run)
        print(f"Ya hay una instalacion en {dest}")
        print(f"Se ACTUALIZA ({old} -> {new_version}). Tus datos, claves, licencias, proyectos y biblioteca no se tocan.")
        if app_running() and not args.dry_run:
            print("\nYTAUTO esta abierto. Cierralo (cierra su ventana negra) y vuelve a abrir el instalador.")
            return APP_OPEN
        src_files = program_files(ROOT, use_git=not args.dry_run)
        previous = load_state(dest).get("files", {})  # instalación antigua sin registro: no se retira nada
        dst_files = hashes_of(dest, set(src_files) | set(previous)) if dest.exists() else {}
        sp = sync_plan(src_files, dst_files, previous)
        print(f"  Archivos: {len(sp['add'])} nuevos, {len(sp['update'])} cambiados, {len(sp['remove'])} retirados, "
              f"{len(sp['same'])} sin cambios")
        if args.dry_run:
            print("  (simulacion: no se copia nada)")
        else:
            backup = apply_sync(ROOT, dest, sp)
            save_state(dest, src_files, new_version)
            if backup:
                print(f"  Habias cambiado {len(sp['backup'])} archivo(s) a mano: copia guardada en {backup}")
            if sp["keep_modified"]:
                print(f"  Se conservan {len(sp['keep_modified'])} archivo(s) modificados que la version nueva ya no usa.")
    else:
        print(f"{'Instalacion nueva' if why == 'nueva' else 'Comprobando la instalacion'} en {dest} (version {new_version})")
        if not args.dry_run and not (dest / STATE_FILE).is_file():
            save_state(dest, program_files(dest), new_version)

    ui_built = (dest / "frontend" / "dist" / "index.html").is_file()  # el paquete ya incluye la interfaz compilada
    npm = shutil.which("npm")
    if not ui_built and npm is None and not args.skip_ui:
        print("AVISO: la interfaz no esta compilada y no se encuentra Node.js (npm). Descarga el programa completo de nuevo.")
    v_ok = not args.dry_run and venv_works(dest)  # la simulacion no ejecuta nada
    d_ok = v_ok and deps_current(dest)
    steps = plan(dest, skip_ui=args.skip_ui, npm=npm, no_claude=args.no_claude, ui_built=ui_built,
                 venv_ok=v_ok, deps_ok=d_ok)
    if v_ok:
        print("\nEntorno de Python: ya existe y funciona (se reutiliza).")
    if d_ok:
        print("Dependencias: sin cambios desde la ultima instalacion (no se reinstalan).")
    for i, (title, cmd, cwd) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {title}")
        print("    >", " ".join(cmd))
        if args.dry_run:
            continue
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            if title.startswith("Comprobar"):
                print("\nLa instalacion termino, pero faltan cosas (lee los avisos de arriba).")
                break
            print(f"\nERROR en el paso: {title} (codigo {result.returncode})")
            return 1
        if title.startswith("Instalar las dependencias de Python"):
            (dest / ".venv" / DEPS_STAMP).write_text(deps_fingerprint(dest), encoding="utf-8")
    if args.dry_run:
        return 0
    if ensure_env(dest):
        print("\nSe ha creado el archivo de configuracion .env (puedes dejarlo como esta).")
    write_registry(reg, dest, new_version)
    if not args.no_accesos:
        for p in write_shortcuts(dest):
            print(f"Acceso directo: {p}")
    print("\nListo. Para usar YTAUTO, abre " + str(launcher(dest)))
    if updating:
        print(f"La carpeta descomprimida ({ROOT}) ya no hace falta: puedes borrarla.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
