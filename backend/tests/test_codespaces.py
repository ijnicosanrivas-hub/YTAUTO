"""Configuración de GitHub Codespaces: usar YTAUTO desde el navegador sin instalar nada en el PC."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request

import pytest

from ytauto.core.settings import REPO_ROOT

DC = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def _cfg():
    return json.loads(DC.read_text(encoding="utf-8"))


def test_devcontainer_is_valid_and_forwards_the_app_privately():
    cfg = _cfg()
    assert "python" in cfg["image"]
    assert "ghcr.io/devcontainers/features/node:1" in cfg["features"]  # la interfaz se compila con Node
    assert 8000 in cfg["forwardPorts"]
    port = cfg["portsAttributes"]["8000"]
    assert port["visibility"] == "private"  # solo tu cuenta de GitHub; nunca público
    assert port["onAutoForward"] == "openBrowser"


def test_devcontainer_scripts_exist_and_are_valid_bash():
    cfg = _cfg()
    for key in ("postCreateCommand", "postStartCommand"):
        script = cfg[key].split()[-1]
        path = REPO_ROOT / script
        assert path.is_file(), f"{key} apunta a un script inexistente: {script}"
        assert os.access(path, os.X_OK)
        assert subprocess.run(["bash", "-n", str(path)], capture_output=True).returncode == 0
        assert b"\r\n" not in path.read_bytes()  # Linux: finales de línea LF


def test_setup_installs_everything_the_app_needs():
    text = (REPO_ROOT / "scripts" / "codespace_setup.sh").read_text(encoding="utf-8")
    for needle in ("ffmpeg", "espeak-ng", "pip install -e .", "npm ci", "npm run build", "claude.ai/install.sh", "set -euo pipefail"):
        assert needle in text, needle
    assert "api_key" not in text.lower() and "token" not in text.lower()  # sin secretos en el repositorio


@pytest.mark.slow
def test_start_script_launches_the_server_once(tmp_path):
    port = 8798
    env = dict(os.environ, YTAUTO_PORT=str(port), YTAUTO_DATA_DIR=str(tmp_path / "d"), YTAUTO_PROJECTS_DIR=str(tmp_path / "p"), YTAUTO_LLM_PROVIDER="local_draft")
    script = str(REPO_ROOT / "scripts" / "codespace_start.sh")
    try:
        first = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=30)
        assert "arrancando" in first.stdout
        ok = False
        for _ in range(120):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                    ok = r.status == 200
                    break
            except OSError:
                continue
        assert ok, "el servidor no respondió"
        second = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=30)
        assert "ya está en marcha" in second.stdout  # idempotente: no lanza una segunda copia
    finally:
        subprocess.run(["pkill", "-f", f"ytauto.api.server --port {port}"], check=False)


def test_start_script_rebuilds_the_ui_when_it_is_missing():
    text = (REPO_ROOT / "scripts" / "codespace_start.sh").read_text(encoding="utf-8")
    assert "frontend/dist/index.html" in text and "npm ci" in text and "npm run build" in text
    assert text.index("npm run build") < text.index("nohup python")  # primero la interfaz, luego el servidor


def test_server_explains_a_missing_ui_instead_of_a_blank_page(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from ytauto.api import server
    from ytauto.app import build_app
    from ytauto.core.settings import Settings
    from ytauto.llm.mock import LocalDraftLLM

    monkeypatch.setattr(server, "FRONTEND_DIST", tmp_path / "no-existe")
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    c = TestClient(server.create_api(build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)))
    r = c.get("/")
    assert r.status_code == 503 and "text/html" in r.headers["content-type"]
    assert "falta la interfaz" in r.text and "npm run build" in r.text
    assert c.get("/api/health").status_code == 200  # la API sigue funcionando
