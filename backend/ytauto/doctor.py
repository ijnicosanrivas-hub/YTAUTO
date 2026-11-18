"""Diagnóstico de la instalación: qué falta y cómo arreglarlo (en el sistema en que se ejecuta)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


from .core.settings import REPO_ROOT, Settings

WINDOWS = sys.platform.startswith("win")
MIN_PYTHON = (3, 11)
MIN_FREE_GB = 5.0


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    critical: bool = True  # un fallo crítico impide producir vídeos


def _fix(windows: str, other: str) -> str:
    return windows if WINDOWS else other


def run_checks(offline: bool = False, settings: Settings | None = None) -> list[Check]:
    checks: list[Check] = []
    v = sys.version_info
    checks.append(Check("Python", (v.major, v.minor) >= MIN_PYTHON, f"{v.major}.{v.minor}.{v.micro}",
                        _fix("Ejecuta INSTALAR_WINDOWS.bat de nuevo (instala Python 3.12)",
                             "Instala Python 3.11 o superior")))

    # FFmpeg: el motor de vídeo (con los filtros que usamos)
    from .providers.rendering.ffmpeg import FFmpegRenderingProvider
    h = FFmpegRenderingProvider().health_check()
    checks.append(Check("FFmpeg", h.ok, h.message.split("Copyright")[0].strip() or h.message,
                        _fix("Ejecuta INSTALAR_WINDOWS.bat de nuevo (descarga FFmpeg dentro del programa)", "Instala FFmpeg 6+ con libass")))

    # Voz: espeak-ng o al menos un modelo Piper
    from .providers.voice.espeak import find_binary
    from .providers.voice.piper import PiperTTSProvider
    espeak = find_binary("espeak-ng")
    piper = PiperTTSProvider().health_check()
    checks.append(Check("Voz", bool(espeak) or piper.ok,
                        "espeak-ng" if espeak else (f"Piper ({piper.message})" if piper.ok else "ninguna instalada"),
                        _fix("Ejecuta INSTALAR_WINDOWS.bat de nuevo (instala la voz)",
                             "sudo apt install espeak-ng")))

    # Claude Code: solo si no se trabaja sin conexión
    claude = shutil.which((settings.claude_bin if settings else "claude"))
    version = ""
    if claude:
        try:
            r = subprocess.run([claude, "--version"], capture_output=True, encoding="utf-8", errors="replace", timeout=30)
            version = (r.stdout or r.stderr).strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    checks.append(Check("Claude Code", bool(claude) or offline,
                        (version or claude or "no instalado") + (" (modo sin Claude)" if offline and not claude else ""),
                        _fix('Ejecuta INSTALAR_WINDOWS.bat de nuevo (instala Claude Code); luego escribe «claude» una vez para iniciar sesión',
                             "curl -fsSL https://claude.ai/install.sh | bash   y luego «claude» para iniciar sesión"),
                        critical=not offline))

    if WINDOWS:  # Claude Code usa Git Bash en Windows
        from .core.tools import find_git_bash
        bash = find_git_bash()
        checks.append(Check("Git Bash", bool(bash), str(bash) if bash else "no encontrado",
                            "Ejecuta INSTALAR_WINDOWS.bat de nuevo (instala Git, que Claude Code necesita en Windows)",
                            critical=False))

    dist = REPO_ROOT / "frontend" / "dist" / "index.html"
    checks.append(Check("Interfaz compilada", dist.exists(), "lista" if dist.exists() else "sin compilar",
                        _fix("Ejecuta INSTALAR_WINDOWS.bat de nuevo", "make ui"), critical=False))

    s = settings or Settings.from_env()
    try:
        s.ensure_dirs()
        probe = s.data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable, where = True, str(s.data_dir)
    except OSError as e:
        writable, where = False, f"{s.data_dir}: {e}"
    checks.append(Check("Carpeta de datos", writable, where,
                        "Mueve el programa a una carpeta donde puedas escribir (p. ej. C:\\YTAUTO)"))

    free_gb = shutil.disk_usage(REPO_ROOT).free / 1e9
    checks.append(Check("Espacio libre", free_gb >= MIN_FREE_GB, f"{free_gb:.0f} GB",
                        "Libera espacio: cada vídeo ocupa unos 250 MB con sus exportaciones", critical=False))

    from .providers.rendering.ffmpeg import BUNDLED_FONT
    checks.append(Check("Fuente incluida", BUNDLED_FONT.exists(), BUNDLED_FONT.name if BUNDLED_FONT.exists() else "falta",
                        "Vuelve a descargar el programa completo", critical=False))
    return checks


def format_report(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "OK " if c.ok else ("FALLO" if c.critical else "AVISO")
        lines.append(f"[{mark}] {c.name}: {c.detail}")
        if not c.ok and c.fix:
            lines.append(f"        Como arreglarlo: {c.fix}")
    bad = [c for c in checks if not c.ok and c.critical]
    lines.append("")
    lines.append("Todo listo para producir videos." if not bad else
                 f"Faltan {len(bad)} cosa(s) imprescindible(s): " + ", ".join(c.name for c in bad))
    return "\n".join(lines)


def doctor(offline: bool = False) -> int:
    checks = run_checks(offline=offline)
    print(format_report(checks))
    return 1 if any(not c.ok and c.critical for c in checks) else 0


def find_free_port(preferred: int = 8000, tries: int = 20, host: str = "127.0.0.1") -> int:
    import socket
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) != 0:  # nadie escucha: libre
                return port
    raise RuntimeError(f"No hay puertos libres entre {preferred} y {preferred + tries - 1}")



