"""Copias de seguridad: base de datos (API de backup de SQLite, consistente en caliente) +
configuración + metadatos de proyectos (JSON). Los medios pesados no se copian por defecto."""
from __future__ import annotations

import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

DEFAULT_KEEP = 10


def backup(db_path: Path, backups_dir: Path, config_dir: Path | None = None, projects_dir: Path | None = None,
           include_media: bool = False, keep: int = DEFAULT_KEEP) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out = backups_dir / f"ytauto-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "ytauto.db"
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(snap))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        with tarfile.open(out, "w:gz") as tar:
            tar.add(snap, arcname="data/ytauto.db")
            if config_dir and config_dir.exists():
                tar.add(config_dir, arcname="config")
            if projects_dir and projects_dir.exists():
                for f in projects_dir.rglob("*"):
                    if f.is_file() and (include_media or f.suffix in (".json", ".md")):
                        tar.add(f, arcname=f"projects/{f.relative_to(projects_dir)}")
    rotate(backups_dir, keep)
    return out


def rotate(backups_dir: Path, keep: int) -> None:
    files = sorted(backups_dir.glob("ytauto-*.tar.gz"))
    for f in files[:-keep] if keep > 0 else []:
        f.unlink()


def restore(archive: Path, target_root: Path) -> Path:
    """Restaura en `target_root` (no sobrescribe sin que el usuario lo elija como destino)."""
    target_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(target_root, filter="data")
    return target_root / "data" / "ytauto.db"
