"""Aplica el tema activo a los prompts de rol de `.claude/agents/*.md`.

Uso: python scripts/aplicar_tema.py [--theme gotham|classic] [--check]
`--check` no escribe: sale con código 1 si algún prompt no coincide con el tema.
Con `classic` elimina los bloques de personaje.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ytauto.core.theme import apply_to_prompt, load_theme  # noqa: E402

AGENTS_DIR = ROOT / ".claude" / "agents"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    theme = load_theme(args.theme)
    stale = []
    for f in sorted(AGENTS_DIR.glob("*.md")):
        old = f.read_text(encoding="utf-8")
        new = apply_to_prompt(old, theme.persona(f.stem))
        if new != old:
            stale.append(f.name)
            if not args.check:
                f.write_text(new, encoding="utf-8", newline="\n")
    print(f"Tema «{theme.id}»: {'desactualizados' if args.check else 'actualizados'}: {stale or 'ninguno'}")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
