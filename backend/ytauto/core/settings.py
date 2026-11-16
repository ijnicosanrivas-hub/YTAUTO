"""Configuración desde variables de entorno y `.env` (sin dependencias externas)."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_dotenv(path: Path | None = None) -> None:
    """Carga `.env` sin sobrescribir variables ya definidas en el entorno."""
    p = path or REPO_ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8-sig").splitlines():  # utf-8-sig: el Bloc de notas de Windows añade BOM
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def force_utf8_console() -> None:
    """La consola de Windows usa cp1252 y fallaría al imprimir tildes, «¿» o flechas."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


class Settings(BaseModel):
    data_dir: Path
    projects_dir: Path
    library_dir: Path
    db_path: Path
    backups_dir: Path
    logs_dir: Path
    llm_provider: str = "claude_cli"  # claude_cli | local_draft
    claude_bin: str = "claude"
    claude_concurrency: int = 1
    claude_timeout_s: int = 600
    fix_major_issues: bool = True
    master_key: str | None = None

    @classmethod
    def from_env(cls, load_env_file: bool = True) -> "Settings":
        if load_env_file:
            load_dotenv()

        def path(var: str, default: str) -> Path:
            p = Path(os.environ.get(var, default))
            return p if p.is_absolute() else (REPO_ROOT / p).resolve()

        data = path("YTAUTO_DATA_DIR", "data")
        return cls(
            data_dir=data,
            projects_dir=path("YTAUTO_PROJECTS_DIR", "projects"),
            library_dir=path("YTAUTO_LIBRARY_DIR", "library"),
            db_path=Path(os.environ.get("YTAUTO_DB_PATH", str(data / "ytauto.db"))),
            backups_dir=Path(os.environ.get("YTAUTO_BACKUPS_DIR", str(REPO_ROOT / "backups"))),
            logs_dir=Path(os.environ.get("YTAUTO_LOGS_DIR", str(data / "logs"))),
            llm_provider=os.environ.get("YTAUTO_LLM_PROVIDER", "claude_cli"),
            claude_bin=os.environ.get("YTAUTO_CLAUDE_BIN", "claude"),
            claude_concurrency=int(os.environ.get("YTAUTO_CLAUDE_CONCURRENCY", "1")),
            claude_timeout_s=int(os.environ.get("YTAUTO_CLAUDE_TIMEOUT", "600")),
            fix_major_issues=os.environ.get("YTAUTO_FIX_MAJOR_ISSUES", "1").strip().lower() not in ("0", "false", "no"),
            master_key=os.environ.get("YTAUTO_MASTER_KEY") or None,
        )

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.projects_dir, self.library_dir, self.backups_dir, self.logs_dir,
                  self.db_path.parent):
            d.mkdir(parents=True, exist_ok=True)
