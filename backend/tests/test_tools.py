"""Herramientas instaladas dentro del programa por INSTALAR_WINDOWS.bat (FFmpeg, voz, Claude Code, Git Bash)."""
from __future__ import annotations

from ytauto.core import tools


def _make(root, rel):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")
    return p


def test_nothing_installed_changes_nothing(tmp_path):
    env = {"PATH": "/usr/bin", "USERPROFILE": str(tmp_path / "sin-nada")}
    assert tools.prepare_environment(tmp_path, env, "win32") == [] and env["PATH"] == "/usr/bin"


def test_windows_local_tools_are_put_first_on_the_path(tmp_path):
    _make(tmp_path, "tools/ffmpeg/bin/ffmpeg.exe")
    _make(tmp_path, "tools/espeak-ng/PFiles/eSpeak NG/espeak-ng.exe")  # el MSI deja la carpeta anidada
    (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
    env = {"PATH": r"C:\Windows\System32", "USERPROFILE": str(tmp_path / "home")}
    added = tools.prepare_environment(tmp_path, env, "win32")
    parts = env["PATH"].split(";")
    assert parts[-1] == r"C:\Windows\System32" and len(added) == 3
    assert parts[0].endswith("bin") and any("eSpeak NG" in p for p in parts) and any(p.endswith(".local\\bin") or p.endswith(".local/bin") for p in parts)
    assert tools.prepare_environment(tmp_path, env, "win32") == []  # idempotente: no duplica nada
    assert env["PATH"].split(";").count(parts[0]) == 1


def test_git_bash_is_found_in_user_or_system_installs_and_exported_for_claude_code(tmp_path):
    bash = _make(tmp_path, "local/Programs/Git/bin/bash.exe")
    env = {"PATH": "", "LOCALAPPDATA": str(tmp_path / "local")}
    added = tools.prepare_environment(tmp_path / "vacio", env, "win32")
    assert env[tools.GIT_BASH_ENV] == str(bash) and any(tools.GIT_BASH_ENV in a for a in added)
    env2 = {"PATH": "", tools.GIT_BASH_ENV: "ya-puesto"}
    tools.prepare_environment(tmp_path / "vacio", env2, "win32")
    assert env2[tools.GIT_BASH_ENV] == "ya-puesto"  # nunca pisa lo que el usuario fijó


def test_linux_only_adds_ffmpeg_and_ignores_windows_things(tmp_path):
    _make(tmp_path, "tools/ffmpeg/bin/ffmpeg")
    _make(tmp_path, "tools/espeak-ng/espeak-ng.exe")
    env = {"PATH": "/usr/bin", "LOCALAPPDATA": str(tmp_path)}
    tools.prepare_environment(tmp_path, env, "linux")
    assert env["PATH"].startswith(str(tmp_path / "tools" / "ffmpeg" / "bin")) and tools.GIT_BASH_ENV not in env
    assert str(tmp_path / "tools" / "espeak-ng") not in env["PATH"]


def test_espeak_finder_uses_the_local_copy(tmp_path, monkeypatch):
    from ytauto.providers.voice import espeak
    exe = _make(tmp_path, "tools/espeak-ng/PFiles/eSpeak NG/espeak-ng.exe")
    monkeypatch.setattr(espeak.shutil, "which", lambda n: None)
    monkeypatch.setattr(espeak, "WINDOWS_PATHS", [])
    monkeypatch.setattr(tools, "find_espeak_dir", lambda root=None: exe.parent)
    assert espeak.find_binary("espeak-ng") == str(exe)


def test_entry_points_prepare_the_environment():
    """Servidor, CLI y diagnóstico pasan por force_utf8_console, que prepara el PATH: si se quita, Windows no ve FFmpeg."""
    import inspect

    from ytauto.core import settings
    assert "prepare_environment" in inspect.getsource(settings.force_utf8_console)
