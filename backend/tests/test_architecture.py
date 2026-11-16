"""Principio innegociable: agentes y orquestador no dependen de proveedores concretos."""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "ytauto"
ALLOWED_PROVIDER_MODULES = {"ytauto.providers.interfaces", "ytauto.providers"}
FORBIDDEN_LIBS = {"elevenlabs", "openai", "runwayml", "replicate", "google", "boto3", "subprocess", "moviepy",
                  "piper", "faster_whisper", "requests", "httpx"}


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    pkg_parts = path.relative_to(PKG.parent).with_suffix("").parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(pkg_parts[: len(pkg_parts) - node.level + 1])
                mods.add(".".join(base + ([node.module] if node.module else [])))
            else:
                mods.add(node.module or "")
    return mods


def test_agents_and_orchestrator_use_only_provider_interfaces():
    offenders = []
    for layer in ("agents", "orchestrator"):
        for f in (PKG / layer).rglob("*.py"):
            for mod in imports_of(f):
                if mod.startswith("ytauto.providers") and mod not in ALLOWED_PROVIDER_MODULES:
                    offenders.append(f"{f.name}: {mod}")
                if mod.split(".")[0] in FORBIDDEN_LIBS:
                    offenders.append(f"{f.name}: {mod}")
    assert offenders == [], f"Dependencias directas de proveedores: {offenders}"


def test_nine_agents_registered():
    from ytauto.agents.registry import build_agents
    agents = build_agents()
    assert len(agents) == 9
    from ytauto.orchestrator.pipeline import PIPELINE
    used = {p.agent for p in PIPELINE if p.agent}
    assert used == set(agents)


def test_agent_definitions_exist_for_claude_code():
    root = PKG.parents[1] / ".claude" / "agents"
    from ytauto.agents.registry import build_agents
    for name, agent in build_agents().items():
        if agent.uses_claude:
            assert (root / f"{name}.md").exists(), f"Falta .claude/agents/{name}.md"
