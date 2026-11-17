"""Acceso desde el iPhone / red local: código de acceso, enlaces y servidor real en modo --lan."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from ytauto.api.lan import LINK_FILE, TOKEN_FILE, ensure_lan_token, is_lan_address, lan_urls, local_addresses
from ytauto.core.settings import REPO_ROOT


def test_token_is_created_once_and_reused(tmp_path):
    t1 = ensure_lan_token(tmp_path)
    assert len(t1) >= 12 and re.fullmatch(r"[A-Za-z0-9_-]+", t1)
    assert ensure_lan_token(tmp_path) == t1  # estable entre arranques: el enlace del móvil sigue valiendo
    assert (tmp_path / TOKEN_FILE).read_text(encoding="utf-8").strip() == t1
    assert ensure_lan_token(tmp_path / "otra") != t1  # cada instalación tiene el suyo


def test_short_or_corrupt_token_file_is_replaced(tmp_path):
    (tmp_path / TOKEN_FILE).write_text("abc\n", encoding="utf-8")
    assert len(ensure_lan_token(tmp_path)) >= 12


@pytest.mark.parametrize("ip,ok", [("192.168.1.20", True), ("10.0.0.5", True), ("172.16.4.9", True), ("172.32.0.1", False),
                                   ("127.0.0.1", False), ("169.254.3.4", False), ("8.8.8.8", False), ("::1", False), ("basura", False)])
def test_only_home_network_addresses_are_offered(ip, ok):
    assert is_lan_address(ip) is ok


def test_urls_carry_the_token_and_local_addresses_are_private():
    assert lan_urls(["192.168.1.20", "10.0.0.5"], 8000, "tok") == ["http://192.168.1.20:8000/?token=tok", "http://10.0.0.5:8000/?token=tok"]
    assert all(is_lan_address(ip) for ip in local_addresses())


def _run_server(tmp_path, *args, port):
    env = dict(os.environ, YTAUTO_DATA_DIR=str(tmp_path / "data"), YTAUTO_PROJECTS_DIR=str(tmp_path / "p"), PYTHONUTF8="1")
    env.pop("YTAUTO_API_TOKEN", None)
    return subprocess.Popen([sys.executable, "-m", "ytauto.api.server", "--offline", "--port", str(port), *args], cwd=REPO_ROOT,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_server_refuses_to_listen_outside_localhost_without_token(tmp_path):
    p = _run_server(tmp_path, "--host", "0.0.0.0", "--no-worker", port=8790)
    out, _ = p.communicate(timeout=60)
    assert p.returncode != 0 and "YTAUTO_API_TOKEN" in out


@pytest.mark.slow
def test_lan_mode_real_server_requires_the_token(tmp_path):
    port = 8795
    p = _run_server(tmp_path, "--lan", "--no-worker", port=port)
    try:
        token = None
        for _ in range(120):
            time.sleep(0.5)
            f = tmp_path / "data" / TOKEN_FILE
            if f.exists() and _get(f"http://127.0.0.1:{port}/api/health") == 200:
                token = f.read_text(encoding="utf-8").strip()
                break
        assert token, "el servidor no arrancó"
        base = f"http://127.0.0.1:{port}"
        assert _get(f"{base}/api/projects") == 401  # sin código: rechazado
        assert _get(f"{base}/api/projects?token=incorrecto") == 401
        assert _get(f"{base}/api/projects?token={token}") == 200
        assert _get(f"{base}/api/theme") == 401 and _get(f"{base}/api/theme?token={token}") == 200
        assert _get(f"{base}/api/agents") == 401
        link_file = tmp_path / "data" / LINK_FILE
        assert link_file.exists() or not local_addresses()  # guarda los enlaces para enviártelos
    finally:
        p.terminate()
        out, _ = p.communicate(timeout=30)
    assert "ACCESO DESDE EL IPHONE" in out and token in out
