"""Instalador incremental: en un equipo nuevo instala todo; si ya hay una instalación, la actualiza sin tocar datos."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("instalar_upd", ROOT / "scripts" / "instalar.py")
inst = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inst)


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


APP_V1 = {"pyproject.toml": "[project]\nname='ytauto'\ndependencies=['a']\n", "backend/ytauto/__init__.py": "v1",
          "config/channels.yaml": "canales: 4\n", "backend/ytauto/viejo.py": "se retira en v2",
          "INICIAR_WINDOWS.bat": "@echo v1", "frontend/dist/index.html": "<html>v1</html>"}
USER_DATA = {"data/secrets/master.key": "CLAVE-MAESTRA", "data/ytauto.db": "base de datos", "library/music/a.mp3": "pista",
             "projects/p1/final.mp4": "video", "tools/ffmpeg/bin/ffmpeg.exe": "ffmpeg", ".env": "MIO=1\n",
             ".venv/bin/python": "#", "backups/b.zip": "copia"}


@pytest.fixture
def installed(tmp_path):
    """Instalación v1 en uso (con datos del usuario) + paquete v2 recién descomprimido en otra carpeta."""
    old = tmp_path / "Escritorio" / "YTAUTO-v1"
    write(old, {**APP_V1, **USER_DATA})
    inst.save_state(old, inst.app_files(old), "v1")
    new = tmp_path / "Descargas" / "YTAUTO-v2"
    write(new, {**APP_V1, "backend/ytauto/__init__.py": "v2", "backend/ytauto/nuevo.py": "nuevo en v2",
                "frontend/dist/index.html": "<html>v2</html>", "VERSION.txt": "v2"})
    (new / "backend/ytauto/viejo.py").unlink()
    return old, new


def run_main(monkeypatch, tmp_path, src: Path, args: list[str], venv_ok=True, deps_ok=True, running=False):
    ran: list[list[str]] = []
    monkeypatch.setattr(inst, "ROOT", src)
    monkeypatch.setattr(inst, "registry_path", lambda *a, **k: tmp_path / "registro" / "instalacion.json")
    monkeypatch.setattr(inst, "legacy_roots", lambda *a, **k: [])
    monkeypatch.setattr(inst, "app_running", lambda *a, **k: running)
    monkeypatch.setattr(inst, "venv_works", lambda *a, **k: venv_ok)
    monkeypatch.setattr(inst, "deps_current", lambda *a, **k: deps_ok)
    monkeypatch.setattr(inst.shutil, "which", lambda name: None)

    def fake_run(cmd, cwd=None, **kw):
        if cmd[0] == "git":  # versión: sin repositorio git en las carpetas de prueba
            return subprocess.CompletedProcess(cmd, 128, "", "")
        ran.append([str(c) for c in cmd])
        if "venv" in cmd:
            (Path(cmd[-1])).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    code = inst.main([*args, "--no-accesos"])
    return code, ran


# ------------------------------------------------------------------ actualización
def test_update_copies_only_changes_and_never_touches_user_data(installed, tmp_path, monkeypatch):
    old, new = installed
    before = {rel: (old / rel).read_text(encoding="utf-8") for rel in USER_DATA}
    code, ran = run_main(monkeypatch, tmp_path, new, ["--destino", str(old)])
    assert code == 0
    assert (old / "backend/ytauto/__init__.py").read_text() == "v2" and (old / "backend/ytauto/nuevo.py").exists()
    assert (old / "frontend/dist/index.html").read_text() == "<html>v2</html>"
    assert not (old / "backend/ytauto/viejo.py").exists()  # lo que la v2 ya no trae, se retira
    assert {rel: (old / rel).read_text(encoding="utf-8") for rel in USER_DATA} == before  # datos intactos
    state = json.loads((old / inst.STATE_FILE).read_text())
    assert state["version"] == "v2" and "backend/ytauto/nuevo.py" in state["files"]
    assert not any("venv" in c for c in ran) and not any("pip" in c for c in ran)  # nada que reinstalar
    assert any(c[-1] == "doctor" or "doctor" in c for c in ran)
    reg = json.loads((tmp_path / "registro" / "instalacion.json").read_text())
    assert Path(reg["root"]) == old and reg["version"] == "v2"


def test_hand_edited_files_are_backed_up_and_obsolete_edited_files_are_kept(installed, tmp_path, monkeypatch):
    old, new = installed
    (old / "backend/ytauto/__init__.py").write_text("v1 retocado a mano")
    (old / "backend/ytauto/viejo.py").write_text("lo cambié yo")
    code, _ = run_main(monkeypatch, tmp_path, new, ["--destino", str(old)])
    assert code == 0 and (old / "backend/ytauto/__init__.py").read_text() == "v2"
    backups = list((old / "backups").glob("actualizacion-*/backend/ytauto/__init__.py"))
    assert backups and backups[0].read_text() == "v1 retocado a mano"
    assert (old / "backend/ytauto/viejo.py").read_text() == "lo cambié yo"  # modificado: no se borra


def test_dependencies_reinstalled_only_when_they_change_or_the_venv_is_broken(installed, tmp_path, monkeypatch):
    old, new = installed
    _, ran = run_main(monkeypatch, tmp_path, new, ["--destino", str(old)], venv_ok=True, deps_ok=False)
    assert any("pip" in c for c in ran) and not any("venv" in c for c in ran)
    assert (old / ".venv" / inst.DEPS_STAMP).read_text() == inst.deps_fingerprint(old)
    _, ran2 = run_main(monkeypatch, tmp_path, new, ["--destino", str(old)], venv_ok=False, deps_ok=False)
    assert any("venv" in c and "--clear" in c for c in ran2) and any("pip" in c for c in ran2)
    assert (old / "data/secrets/master.key").read_text() == "CLAVE-MAESTRA"


def test_refuses_to_update_while_the_app_is_open(installed, tmp_path, monkeypatch):
    old, new = installed
    code, ran = run_main(monkeypatch, tmp_path, new, ["--destino", str(old)], running=True)
    assert code == inst.APP_OPEN == 75 and ran == []
    assert (old / "backend/ytauto/__init__.py").read_text() == "v1"  # nada copiado


def test_new_device_installs_the_whole_pack_in_place(tmp_path, monkeypatch):
    fresh = tmp_path / "nuevo" / "YTAUTO"
    write(fresh, APP_V1)
    code, ran = run_main(monkeypatch, tmp_path, fresh, [], venv_ok=False, deps_ok=False)
    assert code == 0
    assert ran[0][1:4] == ["-m", "venv", "--clear"] and any("pip" in c for c in ran)
    assert json.loads((fresh / inst.STATE_FILE).read_text())["files"]
    assert Path(json.loads((tmp_path / "registro" / "instalacion.json").read_text())["root"]) == fresh


def test_rerun_on_an_up_to_date_install_does_almost_nothing(installed, tmp_path, monkeypatch):
    old, new = installed
    run_main(monkeypatch, tmp_path, new, ["--destino", str(old)])
    sp = inst.sync_plan(inst.app_files(new), inst.app_files(old), inst.load_state(old)["files"])
    assert sp["add"] == sp["update"] == sp["remove"] == [] and sp["same"]


# ------------------------------------------------------------------ dónde está la instalación
def test_destination_prefers_registry_then_legacy_shortcut_then_here(tmp_path):
    src, a, b = tmp_path / "src", tmp_path / "registrada", tmp_path / "antigua"
    for d in (src, a, b):
        write(d, {"pyproject.toml": "x", "backend/ytauto/__init__.py": ""})
    reg = tmp_path / "reg.json"
    assert inst.resolve_destination(src, reg, []) == (src, "nueva")
    assert inst.resolve_destination(src, reg, [b]) == (b, "anterior")
    reg.write_text(json.dumps({"root": str(a)}))
    assert inst.resolve_destination(src, reg, [b]) == (a, "registrada")
    assert inst.resolve_destination(src, reg, [b], here=True) == (src, "aqui")
    assert inst.resolve_destination(src, reg, [b], explicit=b) == (b.resolve(), "explicita")
    reg.write_text(json.dumps({"root": str(tmp_path / "borrada")}))  # la registrada ya no existe
    assert inst.resolve_destination(src, reg, []) == (src, "nueva")


def test_legacy_installs_are_found_through_their_old_shortcuts(tmp_path):
    home = tmp_path / "home"
    win_app = tmp_path / "Mis cosas (1)" / "YTAUTO"
    write(win_app, {"pyproject.toml": "x", "backend/ytauto/__init__.py": "", "INICIAR_WINDOWS.bat": ""})
    write(home, {"Desktop/YTAUTO.bat": f'@start "" "{win_app}/INICIAR_WINDOWS.bat"\r\n'})
    assert inst.legacy_roots("win32", env={}, home=home) == [win_app]
    repo = tmp_path / "repo"
    write(repo, {"pyproject.toml": "x", "backend/ytauto/__init__.py": "", "instaladores/linux/iniciar.sh": ""})
    write(home, {".local/share/applications/ytauto.desktop": f'[Desktop Entry]\nExec=bash "{repo}/instaladores/linux/iniciar.sh"\n'})
    assert repo in inst.legacy_roots("linux", env={}, home=home)


def test_registry_and_shortcuts_point_to_the_installation(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "AppData"), "XDG_CONFIG_HOME": str(tmp_path / "cfg")}
    assert inst.registry_path("win32", env) == tmp_path / "AppData" / "YTAUTO" / "instalacion.json"
    assert inst.registry_path("linux", env) == tmp_path / "cfg" / "ytauto" / "instalacion.json"
    assert inst.registry_path("darwin", {}, home=tmp_path).parts[-3:] == ("Application Support", "YTAUTO", "instalacion.json")
    app = tmp_path / "app"
    write(app, {"INICIAR_WINDOWS.bat": "", "instaladores/linux/iniciar.sh": "", "INICIAR_MAC.command": ""})
    home = tmp_path / "h"
    (home / "Desktop").mkdir(parents=True)
    [w] = inst.write_shortcuts(app, "win32", env={}, home=home)
    assert w.read_bytes() == f'@start "" "{app / "INICIAR_WINDOWS.bat"}"\r\n'.encode()
    [m] = inst.write_shortcuts(app, "darwin", env={}, home=home)
    assert str(app / "INICIAR_MAC.command") in m.read_text() and m.stat().st_mode & 0o111
    [lnx] = inst.write_shortcuts(app, "linux", env={}, home=home)
    assert f'Exec=bash "{app / "instaladores/linux/iniciar.sh"}"' in lnx.read_text()


def test_app_files_skip_user_data_and_local_artifacts(tmp_path):
    write(tmp_path, {**APP_V1, **USER_DATA, "backend/ytauto/__pycache__/x.pyc": "", "frontend/node_modules/a.js": "",
                     inst.STATE_FILE: "{}"})
    files = inst.app_files(tmp_path)
    assert set(files) == set(APP_V1)


# ------------------------------------------------------------------ lanzadores del sistema
def test_system_installers_resolve_the_installation_and_handle_an_open_app():
    bat = (ROOT / "instaladores/windows/INSTALAR_WINDOWS.bat").read_text(encoding="ascii")
    assert ":resolver_destino" in bat and "--resolver-destino" in bat and 'set "HERR=%DEST%\\tools"' in bat
    assert bat.index("call :resolver_destino") < bat.index("[3/6] FFmpeg")  # las herramientas, en la instalada
    assert "if errorlevel 75 if not errorlevel 76 goto app_abierta" in bat
    for name in ("mac/INSTALAR_MAC.command", "linux/instalar.sh"):
        text = (ROOT / "instaladores" / name).read_text(encoding="utf-8")
        assert '"75"' in text and "--resolver-destino" in text and "ytauto.desktop <<" not in text, name
        assert "YTAUTO.command\" <<" not in text, name  # el acceso lo crea scripts/instalar.py


def test_files_the_user_adds_are_never_removed(tmp_path, monkeypatch):
    """La primera instalación solo apunta como «programa» lo que trae el paquete (su manifiesto)."""
    v1 = tmp_path / "v1"
    write(v1, {**APP_V1, "mis_notas.txt": "mías", "guiones/idea.md": "mía"})
    (v1 / inst.PACKAGE_MANIFEST).write_text(json.dumps({"files": {r: "" for r in APP_V1}}))
    run_main(monkeypatch, tmp_path, v1, [], venv_ok=True, deps_ok=True)
    assert set(inst.load_state(v1)["files"]) == set(APP_V1)
    v2 = tmp_path / "v2"
    write(v2, {**APP_V1, "VERSION.txt": "v2"})
    (v2 / inst.PACKAGE_MANIFEST).write_text(json.dumps({"files": {r: "" for r in [*APP_V1, "VERSION.txt"]}}))
    code, _ = run_main(monkeypatch, tmp_path, v2, ["--destino", str(v1)])
    assert code == 0 and (v1 / "mis_notas.txt").read_text() == "mías" and (v1 / "guiones/idea.md").exists()
    assert (v1 / "VERSION.txt").read_text() == "v2"


def test_package_zip_carries_its_file_list(tmp_path):
    import zipfile
    spec = importlib.util.spec_from_file_location("emp", ROOT / "scripts" / "empaquetar.py")
    emp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emp)
    write(tmp_path / "repo", {"a.txt": "A", "sub/b.txt": "B"})
    out = tmp_path / "p.zip"
    emp.write_zip(out, {"YTAUTO/a.txt": "a.txt", "YTAUTO/sub/b.txt": "sub/b.txt"}, root=tmp_path / "repo", version="v9")
    with zipfile.ZipFile(out) as z:
        man = json.loads(z.read("YTAUTO/" + inst.PACKAGE_MANIFEST))
    assert man["version"] == "v9" and set(man["files"]) == {"a.txt", "sub/b.txt", "VERSION.txt"}
