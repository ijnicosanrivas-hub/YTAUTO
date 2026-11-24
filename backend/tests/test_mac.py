"""Instalación en macOS: scripts .command, rutas de Homebrew y voz del sistema (solo uso personal)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ytauto.core import tools
from ytauto.providers.voice import macos_say

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ["INSTALAR_MAC.command", "INICIAR_MAC.command", "INICIAR_MAC_SIN_CLAUDE.command", "DIAGNOSTICO_MAC.command"]


@pytest.mark.parametrize("name", COMMANDS)
def test_command_files_are_valid_bash_with_unix_line_endings(name):
    raw = (ROOT / name).read_bytes()
    assert raw.startswith(b"#!/bin/bash\n") and b"\r" not in raw  # con CRLF el Terminal de macOS no los ejecuta
    assert subprocess.run(["bash", "-n", str(ROOT / name)]).returncode == 0
    assert "sudo " not in raw.decode("utf-8")  # nunca pide privilegios por su cuenta (Homebrew los pide él mismo)


@pytest.mark.parametrize("name", COMMANDS)
def test_command_files_are_executable_in_the_zip(name):
    # git archive conserva el bit de ejecución: sin él, el doble clic en el Finder no hace nada
    mode = subprocess.run(["git", "ls-files", "-s", name], cwd=ROOT, capture_output=True, text=True).stdout.split()[0]
    assert mode == "100755"


def test_installer_uses_homebrew_for_ffmpeg_voice_and_python_and_the_official_claude_installer():
    text = (ROOT / "INSTALAR_MAC.command").read_text(encoding="utf-8")
    for pkg in ("python@3.12", "ffmpeg", "espeak-ng"):
        assert f"instalar_brew {pkg}" in text
    assert "https://claude.ai/install.sh" in text and "scripts/instalar.py" in text
    assert "com.apple.quarantine" in text  # sin esto macOS bloquea los demás .command descargados
    assert "/opt/homebrew/bin/brew" in text and "/usr/local/bin/brew" in text  # Apple Silicon e Intel


def test_launchers_load_homebrew_and_claude_paths():
    for name in COMMANDS[1:]:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "/opt/homebrew/bin/brew" in text and "shellenv" in text and "$HOME/.local/bin" in text


def test_tool_dirs_on_mac_include_homebrew_and_claude(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    dirs = tools.local_tool_dirs(tmp_path, {"HOME": str(home)}, platform="darwin")
    assert home / ".local" / "bin" in dirs
    assert not any(str(d).startswith("/opt/homebrew") for d in tools.local_tool_dirs(tmp_path, {"HOME": str(home)}, platform="linux"))


SAY_LIST = """Alex                en_US    # Most people recognize me by my voice.
Eddy (Spanish (Spain)) es_ES    # Hola, me llamo Eddy.
Jorge               es_ES    # Hola, me llamo Jorge y soy una voz española.
Mónica              es_ES    # Hola, me llamo Mónica y soy una voz española.
Paulina             es_MX    # Hola, me llamo Paulina y soy una voz mexicana.
"""


def test_parse_and_choose_system_voices():
    voices = macos_say.parse_voices(SAY_LIST)
    assert ("Eddy (Spanish (Spain))", "es_ES") in voices and len(voices) == 5
    assert macos_say.choose_voice(voices, "es") == "Mónica"
    assert macos_say.choose_voice(voices, "es", wanted="Paulina") == "Paulina"
    assert macos_say.choose_voice(voices, "en") == "Alex"
    assert macos_say.choose_voice(voices, "de") is None


def test_system_voice_is_opt_in_and_marked_non_commercial():
    # La licencia de macOS solo permite sus voces para uso personal no comercial: nunca se activa sola.
    assert macos_say.MacSayTTSProvider.auto_register is False
    src = (ROOT / "backend/ytauto/providers/voice/macos_say.py").read_text(encoding="utf-8")
    assert "commercial_use=False" in src
    if os.uname().sysname != "Darwin":
        assert macos_say.MacSayTTSProvider().health_check().ok is False


def test_system_voice_not_seeded_by_default(tmp_path):
    from ytauto.providers.bootstrap import build_provider_system
    from ytauto.db.schema import make_engine
    system = build_provider_system(make_engine(tmp_path / "x.db"), tmp_path, None)
    assert "macos_say" not in {p.adapter for p in system.registry.list()}
    assert "espeak" in {p.adapter for p in system.registry.list()}
