"""Crea los paquetes descargables de YTAUTO (uno por sistema) a partir de los archivos del repositorio.

Cada paquete lleva la aplicación completa y, arriba del todo, los lanzadores de SU sistema (los de
`instaladores/<sistema>/`), para que al descomprimir se vea directamente el instalador:

    YTAUTO-windows.zip   YTAUTO-mac.zip   YTAUTO-linux.zip   YTAUTO-completo.zip   YTAUTO-web-demo.zip

`YTAUTO-completo.zip` es el repositorio tal cual (todos los instaladores dentro de `instaladores/`).
`YTAUTO-web-demo.zip` es la demostración estática para Netlify/Telegram (requiere `npm run build:demo` antes).
Conserva el permiso de ejecución de los `.command` y `.sh` (sin él, el doble clic en Mac no hace nada).

Uso:  python scripts/empaquetar.py [--salida paquetes] [--version v1.2.0]
"""
from __future__ import annotations

import argparse
import datetime as dt
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "YTAUTO"
SISTEMAS = ("windows", "mac", "linux")
GUIA_MOVIL = "instaladores/movil/LEEME.md"


def tracked_files(root: Path = ROOT) -> list[str]:
    """Archivos versionados (lo que hay en git), con su contenido actual en disco."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return sorted(f for f in out.decode("utf-8").split("\0") if f and (root / f).is_file())


def plan(files: list[str], sistema: str) -> dict[str, str]:
    """Ruta dentro del ZIP → ruta en el repositorio. Función pura (se prueba sin crear nada)."""
    base = {f"{PREFIX}/{f}": f for f in files if not f.startswith((".github/", "instaladores/"))}
    if sistema == "completo":
        base.update({f"{PREFIX}/{f}": f for f in files if f.startswith("instaladores/")})
        return base
    propios = f"instaladores/{sistema}/"
    for f in files:
        if f.startswith(propios):
            base[f"{PREFIX}/{f[len(propios):]}"] = f
    if GUIA_MOVIL in files:
        base[f"{PREFIX}/USAR_DESDE_EL_MOVIL.md"] = GUIA_MOVIL
    return base


def _info(name: str, src: Path) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=dt.datetime.fromtimestamp(src.stat().st_mtime).timetuple()[:6])
    executable = src.suffix in (".command", ".sh") or bool(src.stat().st_mode & stat.S_IXUSR)
    info.external_attr = ((0o100755 if executable else 0o100644) & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def write_zip(dest: Path, mapping: dict[str, str], root: Path = ROOT, version: str = "") -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(mapping):
            src = root / mapping[name]
            z.writestr(_info(name, src), src.read_bytes())
        if version:
            z.writestr(f"{PREFIX}/VERSION.txt", f"{version}\n")
    return len(mapping)


def write_web(dest: Path, folder: Path) -> int:
    files = [p for p in sorted(folder.rglob("*")) if p.is_file()]
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(folder).as_posix())
    return len(files)


def version_label(root: Path = ROOT) -> str:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "?"
    return f"{commit} · {dt.date.today().isoformat()}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crea los paquetes de YTAUTO por sistema")
    ap.add_argument("--salida", default=str(ROOT / "paquetes"))
    ap.add_argument("--version", default="")
    a = ap.parse_args(argv)
    out = Path(a.salida)
    version = a.version or version_label()
    files = tracked_files()
    for sistema in (*SISTEMAS, "completo"):
        n = write_zip(out / f"YTAUTO-{sistema}.zip", plan(files, sistema), version=version)
        print(f"YTAUTO-{sistema}.zip  ({n} archivos)")
    demo = ROOT / "frontend" / "dist-demo"
    if (demo / "index.html").is_file():
        print(f"YTAUTO-web-demo.zip  ({write_web(out / 'YTAUTO-web-demo.zip', demo)} archivos)")
    else:
        print("(sin demo web: ejecuta  cd frontend && npm run build:demo  para incluirla)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
