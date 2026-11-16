"""Espacio de trabajo de un proyecto: artefactos en disco y memoria persistente."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import utcnow

PROJECT_SUBDIRS = (
    "planning", "scripts", "resources", "voice", "scenes", "sound", "review", "exports", "reports",
)

T = TypeVar("T", bound=BaseModel)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


class Workspace:
    """Directorio `projects/<id>/` con subcarpetas por fase."""

    def __init__(self, root: Path, project_id: str):
        self.project_id = project_id
        self.root = (root / project_id).resolve()
        for sub in PROJECT_SUBDIRS:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def dir(self, sub: str) -> Path:
        if sub not in PROJECT_SUBDIRS:
            raise ValueError(f"Subdirectorio no permitido: {sub}")
        return self.root / sub

    def resolve_inside(self, path: Path) -> Path:
        """Valida que una ruta esté dentro del proyecto (evita path traversal)."""
        p = Path(path).resolve()
        if self.root not in p.parents and p != self.root:
            raise PermissionError(f"Ruta fuera del proyecto: {path}")
        return p

    # ---- artefactos JSON
    def _artifact_path(self, sub: str, name: str) -> Path:
        return self.dir(sub) / f"{name}.json"

    def save(self, sub: str, name: str, data: BaseModel | dict | list) -> Path:
        path = self._artifact_path(sub, name)
        if isinstance(data, BaseModel):
            text = data.model_dump_json(indent=2)
        else:
            text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        atomic_write_text(path, text)
        return path

    def load(self, sub: str, name: str, model: type[T] | None = None) -> Any:
        path = self._artifact_path(sub, name)
        if not path.exists():
            raise FileNotFoundError(f"Artefacto inexistente: {sub}/{name}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return model.model_validate(raw) if model else raw

    def has(self, sub: str, name: str) -> bool:
        return self._artifact_path(sub, name).exists()


class ProjectMemory:
    """Memoria persistente: decisiones y resúmenes entre fases (contexto compacto para Claude)."""

    def __init__(self, workspace: Workspace):
        self.path = workspace.root / "memory.json"
        self._data: dict[str, Any] = {"summaries": {}, "decisions": [], "notes": []}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        atomic_write_text(self.path, json.dumps(self._data, ensure_ascii=False, indent=2, default=str))

    def set_summary(self, phase: str, summary: str) -> None:
        self._data["summaries"][phase] = {"text": summary, "at": utcnow().isoformat()}
        self._flush()

    def add_decision(self, who: str, decision: str) -> None:
        self._data["decisions"].append({"by": who, "decision": decision, "at": utcnow().isoformat()})
        self._flush()

    def summaries(self) -> dict[str, str]:
        return {k: v["text"] for k, v in self._data["summaries"].items()}

    def decisions(self) -> list[dict[str, Any]]:
        return list(self._data["decisions"])

    def digest(self, max_chars: int = 2000) -> str:
        """Resumen compacto para incluir en prompts sin enviar todo el historial."""
        lines = [f"- {k}: {v}" for k, v in self.summaries().items()]
        lines += [f"- decisión ({d['by']}): {d['decision']}" for d in self.decisions()[-10:]]
        text = "\n".join(lines)
        return text[-max_chars:]
