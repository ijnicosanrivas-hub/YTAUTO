"""Herramientas locales de la instalación en Windows.

El instalador deja FFmpeg y eSpeak NG dentro de `tools/` (sin permisos de administrador y sin tocar el PATH del
sistema). Al arrancar, YTAUTO las añade al PATH de su propio proceso, localiza Claude Code (`~/.local/bin`) y Git Bash
(que Claude Code necesita en Windows). Todo es de solo lectura sobre el disco y no hace nada si no encuentra nada.
"""
from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

from .settings import REPO_ROOT

GIT_BASH_ENV = "CLAUDE_CODE_GIT_BASH_PATH"


def _is_windows(platform: str | None) -> bool:
    return (platform or sys.platform).startswith("win")


def find_espeak_dir(root: Path = REPO_ROOT) -> Path | None:
    """Carpeta con `espeak-ng.exe` dentro de `tools/espeak-ng` (el instalador MSI la deja anidada)."""
    base = root / "tools" / "espeak-ng"
    if not base.is_dir():
        return None
    for exe in sorted(base.rglob("espeak-ng.exe")):
        return exe.parent
    return None


def find_git_bash(env: MutableMapping[str, str] | None = None, root: Path = REPO_ROOT) -> Path | None:
    """`bash.exe` de Git para Windows (instalado para todos, solo para el usuario o dentro de tools/)."""
    env = os.environ if env is None else env
    explicit = env.get(GIT_BASH_ENV)
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    candidates: list[Path] = []
    for var, sub in (("ProgramFiles", "Git"), ("ProgramW6432", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        if env.get(var):
            candidates.append(Path(env[var]) / sub / "bin" / "bash.exe")
    candidates.append(root / "tools" / "git" / "bin" / "bash.exe")
    return next((c for c in candidates if c.is_file()), None)


def local_tool_dirs(root: Path = REPO_ROOT, env: MutableMapping[str, str] | None = None, platform: str | None = None) -> list[Path]:
    env = os.environ if env is None else env
    windows = _is_windows(platform)
    dirs: list[Path] = []
    ffmpeg = root / "tools" / "ffmpeg" / "bin"
    if (ffmpeg / ("ffmpeg.exe" if windows else "ffmpeg")).is_file():
        dirs.append(ffmpeg)
    if windows:
        espeak = find_espeak_dir(root)
        if espeak:
            dirs.append(espeak)
        home = env.get("USERPROFILE")
        claude = (Path(home) if home else Path.home()) / ".local" / "bin"
        if claude.is_dir():
            dirs.append(claude)
    return dirs


def prepare_environment(root: Path = REPO_ROOT, env: MutableMapping[str, str] | None = None, platform: str | None = None) -> list[str]:
    """Añade las herramientas locales al PATH de este proceso y fija la ruta de Git Bash. Devuelve lo añadido."""
    env = os.environ if env is None else env
    windows = _is_windows(platform)
    sep = ";" if windows else ":"
    current = [p for p in env.get("PATH", "").split(sep) if p]
    lowered = {p.lower().rstrip("\\/") for p in current}
    added: list[str] = []
    for d in local_tool_dirs(root, env, platform):
        if str(d).lower().rstrip("\\/") not in lowered:
            added.append(str(d))
    if added:
        env["PATH"] = sep.join(added + current)
    if windows and not env.get(GIT_BASH_ENV):
        bash = find_git_bash(env, root)
        if bash:
            env[GIT_BASH_ENV] = str(bash)
            added.append(f"{GIT_BASH_ENV}={bash}")
    return added
