"""Repositorio organizado por sistemas y paquetes descargables (Windows, Mac, Linux, completo, demo web)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("empaquetar", ROOT / "scripts" / "empaquetar.py")
emp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emp)

FILES = ["pyproject.toml", "backend/ytauto/app.py", ".github/workflows/publicar.yml", "instaladores/windows/INSTALAR_WINDOWS.bat",
         "instaladores/windows/LEEME.txt", "instaladores/mac/INSTALAR_MAC.command", "instaladores/linux/instalar.sh",
         "instaladores/movil/LEEME.md", "instaladores/web/LEEME.md"]


def test_each_package_puts_its_own_installers_on_top_and_hides_the_others():
    win = emp.plan(FILES, "windows")
    assert win["YTAUTO/INSTALAR_WINDOWS.bat"] == "instaladores/windows/INSTALAR_WINDOWS.bat"
    assert win["YTAUTO/LEEME.txt"] == "instaladores/windows/LEEME.txt"
    assert win["YTAUTO/USAR_DESDE_EL_MOVIL.md"] == "instaladores/movil/LEEME.md"
    assert not any("mac" in k or "linux" in k or ".github" in k for k in win)
    assert "YTAUTO/backend/ytauto/app.py" in win and "YTAUTO/pyproject.toml" in win
    assert "YTAUTO/INSTALAR_MAC.command" in emp.plan(FILES, "mac")
    assert "YTAUTO/instalar.sh" in emp.plan(FILES, "linux")


def test_complete_package_is_the_repository_layout():
    full = emp.plan(FILES, "completo")
    assert "YTAUTO/instaladores/mac/INSTALAR_MAC.command" in full and "YTAUTO/INSTALAR_MAC.command" not in full


def test_zip_keeps_execute_permission_for_mac_and_linux(tmp_path):
    files = ["instaladores/mac/INSTALAR_MAC.command", "instaladores/linux/instalar.sh", "pyproject.toml"]
    dest = tmp_path / "x.zip"
    emp.write_zip(dest, {f"YTAUTO/{Path(f).name}": f for f in files}, version="abc")
    z = zipfile.ZipFile(dest)
    assert z.getinfo("YTAUTO/INSTALAR_MAC.command").external_attr >> 16 == 0o100755
    assert z.getinfo("YTAUTO/instalar.sh").external_attr >> 16 == 0o100755
    assert z.getinfo("YTAUTO/pyproject.toml").external_attr >> 16 == 0o100644
    assert z.read("YTAUTO/VERSION.txt") == b"abc\n"


def test_repository_root_is_tidy():
    # Los lanzadores viven en instaladores/<sistema>/, no sueltos en la raíz
    loose = [p.name for p in ROOT.iterdir() if p.suffix in (".bat", ".command", ".sh")]
    assert loose == []
    for folder in ("windows", "mac", "linux", "movil", "web"):
        assert any((ROOT / "instaladores" / folder).glob("LEEME*")), folder


@pytest.mark.parametrize("name", ["instalar.sh", "iniciar.sh", "iniciar_movil.sh", "iniciar_sin_claude.sh", "diagnostico.sh"])
def test_linux_scripts_are_valid_executable_bash(name):
    path = ROOT / "instaladores" / "linux" / name
    raw = path.read_bytes()
    assert raw.startswith(b"#!/bin/bash\n") and b"\r" not in raw
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
    mode = subprocess.run(["git", "ls-files", "-s", f"instaladores/linux/{name}"], cwd=ROOT, capture_output=True, text=True).stdout.split()[0]
    assert mode == "100755"


def test_linux_installer_covers_the_common_package_managers():
    text = (ROOT / "instaladores" / "linux" / "instalar.sh").read_text(encoding="utf-8")
    assert all(m in text for m in ("apt-get", "dnf", "pacman", "espeak-ng", "ffmpeg", "claude.ai/install.sh", "scripts/instalar.py"))


def test_app_installs_on_phones_and_tablets():
    manifest = json.loads((ROOT / "frontend" / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone" and {i["sizes"] for i in manifest["icons"]} == {"192x192", "512x512"}
    for icon in ("icono-192.png", "icono-512.png", "apple-touch-icon.png"):
        assert (ROOT / "frontend" / "public" / icon).is_file()
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html and 'rel="apple-touch-icon"' in html


def test_release_workflow_publishes_every_package():
    wf = (ROOT / ".github" / "workflows" / "publicar.yml").read_text(encoding="utf-8")
    assert "scripts/empaquetar.py" in wf and "build:demo" in wf and "contents: write" in wf
    assert "ultima-version" in wf and "gh release" in wf
