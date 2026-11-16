"""Almacenamiento en el sistema de ficheros local."""
from __future__ import annotations

import shutil
from pathlib import Path

from ...core.settings import REPO_ROOT
from ..interfaces import HealthStatus, StorageProvider


class LocalStorageProvider(StorageProvider):
    """Guarda ficheros en una carpeta local (por defecto data/storage)."""
    name = "local_storage"
    display_name = "Disco local"
    default_params = {"root": ""}

    @property
    def root(self) -> Path:
        return Path(self.params["root"] or REPO_ROOT / "data" / "storage").resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise PermissionError(f"Clave fuera del almacenamiento: {key}")
        return p

    def health_check(self) -> HealthStatus:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            return HealthStatus(ok=True, message=str(self.root))
        except OSError as e:
            return HealthStatus(ok=False, message=str(e))

    def put(self, local_path: Path, key: str) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)
        return dest.as_uri()

    def get(self, key: str, dest: Path) -> Path:
        shutil.copy2(self._path(key), dest)
        return Path(dest)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
