"""Instalador y scripts de Windows: lo que se puede comprobar sin un Windows (la lógica va en Python)."""
from __future__ import annotations

import importlib.util
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(path: str):
    spec = importlib.util.spec_from_file_location("instalar", ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inst = load("scripts/instalar.py")


def test_plan_uses_the_windows_virtualenv_layout_and_the_right_steps(tmp_path):
    steps = inst.plan(tmp_path, platform="win32", npm=r"C:\Program Files\nodejs\npm.CMD")
    py = tmp_path / ".venv" / "Scripts" / "python.exe"
    assert [s[0] for s in steps] == ["Crear el entorno de Python (.venv)", "Instalar las dependencias de Python",
                                     "Instalar las dependencias de la interfaz", "Compilar la interfaz",
                                     "Comprobar la instalacion"]
    assert steps[1][1][0] == str(py) and steps[1][1][-2:] == ["-e", "."]
    assert steps[2][2] == tmp_path / "frontend" and steps[3][1][-2:] == ["run", "build"]
    assert steps[-1][1] == [str(py), "-m", "ytauto", "doctor"]


def test_plan_on_linux_uses_bin_python_and_can_skip_the_ui_and_claude(tmp_path):
    steps = inst.plan(tmp_path, platform="linux", skip_ui=True, npm="/usr/bin/npm", no_claude=True)
    assert steps[1][1][0] == str(tmp_path / ".venv" / "bin" / "python")
    assert len(steps) == 3 and steps[-1][1][-1] == "--no-claude"
    assert len(inst.plan(tmp_path, npm=None)) == 3  # sin npm no hay pasos de interfaz


def test_env_file_is_created_once_and_never_overwritten(tmp_path):
    (tmp_path / ".env.example").write_text("A=1\n", encoding="utf-8")
    assert inst.ensure_env(tmp_path) is True and (tmp_path / ".env").read_text(encoding="utf-8") == "A=1\n"
    (tmp_path / ".env").write_text("A=2 # mío\n", encoding="utf-8")
    assert inst.ensure_env(tmp_path) is False and "mío" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_dry_run_changes_nothing(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("dry-run no debe ejecutar nada")

    monkeypatch.setattr(inst.subprocess, "run", boom)
    assert inst.main(["--dry-run", "--skip-ui"]) == 0
    assert "pip install" in capsys.readouterr().out


# ---------------------------------------------------------------- scripts de Windows (revisión estática)
BATS = ["INSTALAR_WINDOWS.bat", "INICIAR_WINDOWS.bat", "INICIAR_WINDOWS_SIN_CLAUDE.bat", "DIAGNOSTICO_WINDOWS.bat"]


@pytest.mark.parametrize("name", BATS)
def test_bat_files_are_crlf_and_pure_ascii(name):
    raw = (ROOT / name).read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")  # solo CRLF: con LF los «goto» de cmd fallan
    raw.decode("ascii")  # sin tildes: cmd.exe las corrompe según la página de códigos


def test_powershell_installer_is_crlf_utf8_with_bom_and_uses_the_verified_commands():
    raw = (ROOT / "scripts" / "instalar_windows.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw  # BOM: Windows PowerShell 5.1 lee si no ANSI
    text = raw.decode("utf-8-sig")
    for wanted in ("Python.Python.3.12", "Gyan.FFmpeg", "OpenJS.NodeJS.LTS", "eSpeak-NG.eSpeak-NG",
                   "https://claude.ai/install.ps1", "scripts\\instalar.py", "--accept-package-agreements"):
        assert wanted in text, wanted
    assert "&&" not in text  # sintaxis de bash: no existe en PowerShell 5.1
    assert text.count("{") == text.count("}") and text.count("(") == text.count(")")  # llaves y paréntesis equilibrados


def test_start_scripts_run_the_doctor_first_and_force_utf8():
    for name, flags in (("INICIAR_WINDOWS.bat", ("doctor", "ytauto.api.server --open")),
                        ("INICIAR_WINDOWS_SIN_CLAUDE.bat", ("doctor --no-claude", "--offline --open"))):
        text = (ROOT / name).read_text(encoding="ascii")
        assert "set PYTHONUTF8=1" in text and r".venv\Scripts\python.exe" in text and "cd /d" in text
        assert all(f in text for f in flags)
        labels = set(re.findall(r"^:(\w+)", text, re.M))
        targets = set(re.findall(r"goto (\w+)", text))
        assert targets <= labels, targets - labels  # ningún «goto» apunta a una etiqueta inexistente


def test_gitattributes_keeps_windows_line_endings():
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.bat text eol=crlf" in text and "*.ps1 text eol=crlf" in text


# ---------------------------------------------------------------- servidor y diagnóstico
def test_free_port_skips_an_occupied_port():
    from ytauto.doctor import find_free_port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        busy = s.getsockname()[1]
        assert find_free_port(busy) == busy + 1 or find_free_port(busy) > busy


def test_doctor_reports_every_check_with_a_fix_and_fails_on_critical_problems(monkeypatch):
    from ytauto import doctor
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)  # nada instalado
    monkeypatch.setattr(doctor, "WINDOWS", True)
    checks = doctor.run_checks()
    by = {c.name: c for c in checks}
    assert not by["Claude Code"].ok and "install.ps1" in by["Claude Code"].fix
    assert "winget" in by["FFmpeg"].fix and "INSTALAR_WINDOWS.bat" in by["FFmpeg"].fix
    report = doctor.format_report(checks)
    assert "FALLO" in report and "Como arreglarlo" in report and "Faltan" in report
    offline = {c.name: c for c in doctor.run_checks(offline=True)}
    assert offline["Claude Code"].ok  # en modo sin Claude no es obligatorio


def test_doctor_command_exit_codes(monkeypatch, capsys):
    from ytauto import cli, doctor
    monkeypatch.setattr(doctor, "run_checks", lambda offline=False, settings=None: [
        doctor.Check("FFmpeg", False, "no", "instálalo", critical=True)])
    assert cli.main(["doctor"]) == 1
    monkeypatch.setattr(doctor, "run_checks", lambda offline=False, settings=None: [doctor.Check("Todo", True, "ok")])
    assert cli.main(["doctor"]) == 0 and "Todo listo" in capsys.readouterr().out


def test_the_server_module_accepts_open_flag():
    out = subprocess.run([sys.executable, "-m", "ytauto.api.server", "--help"], capture_output=True,
                         encoding="utf-8", errors="replace", cwd=ROOT / "backend", timeout=60)
    assert "--open" in out.stdout and out.returncode == 0
