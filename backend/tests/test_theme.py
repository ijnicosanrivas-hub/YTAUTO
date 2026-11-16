"""Tema de personajes (Gotham): validez, API y coherencia con los prompts de rol."""
from __future__ import annotations

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from ytauto.agents.registry import AGENT_CLASSES
from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.settings import REPO_ROOT, Settings
from ytauto.core.theme import (QUOTE_STATES, THEME_DIR, Persona, Theme, apply_to_prompt, available_themes,
                               load_theme)
from ytauto.llm.mock import LocalDraftLLM

NAMES = [c.name for c in AGENT_CLASSES]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
GOTHAM = {"chief": "Batman", "director": "El Acertijo", "scriptwriter": "El Joker", "resources": "Catwoman",
          "voice": "Bane", "editor": "Nightwing", "sound": "El Pingüino", "reviewer": "Dos Caras",
          "publisher": "Harley Quinn"}


def test_gotham_theme_is_valid_and_complete():
    t = load_theme("gotham")
    assert t.id == "gotham" and t.problems(NAMES) == []
    assert {n: t.agents[n].character for n in NAMES} == GOTHAM
    for p in t.agents.values():
        assert set(QUOTE_STATES) <= set(p.quotes)


def test_classic_theme_has_no_characters_and_is_valid():
    t = load_theme("classic")
    assert t.agents == {} and t.problems(NAMES) == []
    assert "classic" in available_themes() and "gotham" in available_themes()


def test_problems_detects_broken_themes():
    t = load_theme("gotham")
    broken = t.model_copy(deep=True)
    del broken.agents["voice"]
    assert any("faltan agentes" in x for x in broken.problems(NAMES))
    dup = t.model_copy(deep=True)
    dup.agents["voice"].color = dup.agents["editor"].color
    assert "color repetido" in dup.problems(NAMES)
    mute = t.model_copy(deep=True)
    mute.agents["voice"].quotes["error"] = " "
    assert any("faltan frases" in x for x in mute.problems(NAMES))
    bad = t.model_copy(deep=True)
    bad.agents["voice"].color = "naranja"
    assert any("color inválido" in x for x in bad.problems(NAMES))


def test_load_theme_never_breaks(tmp_path, monkeypatch):
    assert load_theme("no-existe").id == "classic"  # desconocido → clásico
    assert load_theme("../../etc/passwd").id == "classic"  # sin recorrer rutas
    (tmp_path / "classic.yaml").write_text("id: [roto", encoding="utf-8")
    assert load_theme("classic", directory=tmp_path).id == "classic"  # YAML roto → tema de emergencia
    monkeypatch.setenv("YTAUTO_THEME", "classic")
    assert load_theme().id == "classic"
    monkeypatch.delenv("YTAUTO_THEME")
    assert load_theme().id == "gotham"  # por defecto


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    app = build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)
    return lambda theme=None: TestClient(create_api(app, theme=theme))


def test_api_exposes_theme(client):
    d = client(load_theme("gotham")).get("/api/theme").json()
    assert d["id"] == "gotham" and d["agents"]["chief"]["character"] == "Batman"
    c = client(load_theme("classic")).get("/api/theme").json()
    assert c["id"] == "classic" and c["agents"] == {}


def test_theme_does_not_change_agent_state(client):
    """Los datos funcionales de /api/agents son idénticos con cualquier tema."""
    a = client(load_theme("gotham")).get("/api/agents").json()
    b = client(load_theme("classic")).get("/api/agents").json()
    assert a == b and [x["name"] for x in a["agents"]] == NAMES


def test_role_prompts_match_active_theme():
    """Los .md de `.claude/agents` llevan exactamente el bloque del tema por defecto (si no: scripts/aplicar_tema.py)."""
    t = load_theme("gotham")
    for name in NAMES:
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        assert apply_to_prompt(text, t.persona(name)) == text, f"{name}.md desactualizado"
        assert GOTHAM[name] in text and "ÚNICAMENTE en los campos explicativos" in text and "como si esta personalidad no existiera" in text


def test_apply_to_prompt_is_idempotent_and_reversible():
    p = load_theme("gotham").persona("chief")
    raw = '---\nname: chief\nmodel: sonnet\n---\n\nEres el jefe.\n'  # formato real de los roles
    once = apply_to_prompt(raw, p)
    assert once.startswith("---\nname: chief\nmodel: sonnet\n---\n") and "Batman" in once
    assert once.count("tema:inicio") == 1 and apply_to_prompt(once, p) == once
    assert apply_to_prompt(once, None) == raw  # quitar el bloque restituye el original
    assert apply_to_prompt("sin frontmatter", p) == "sin frontmatter"


def test_prompt_block_never_touches_output_schema():
    """El bloque de personalidad excluye explícitamente el contenido del vídeo y el esquema JSON."""
    block = Persona(**load_theme("gotham").agents["scriptwriter"].model_dump()).persona
    assert block and "{" not in block and "json" not in block.lower()


def test_aplicar_tema_check_script():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "aplicar_tema.py"), "--check", "--theme", "gotham"],
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stdout + r.stderr


def test_theme_files_are_utf8_without_secrets():
    for f in THEME_DIR.glob("*.yaml"):
        text = f.read_text(encoding="utf-8")
        assert Theme.model_validate(__import__("yaml").safe_load(text))
        assert "api_key" not in text.lower() and "token" not in text.lower()


def test_every_real_role_prompt_round_trips():
    """Quitar el bloque de cada rol real y volver a ponerlo deja el fichero idéntico."""
    t = load_theme("gotham")
    for name in NAMES:
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        plain = apply_to_prompt(text, None)
        assert "tema:inicio" not in plain and plain.startswith("---\n")
        assert apply_to_prompt(plain, t.persona(name)) == text
