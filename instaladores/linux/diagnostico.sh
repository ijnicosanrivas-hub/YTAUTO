#!/bin/bash
cd "$(dirname "$0")" || exit 1
[ -f pyproject.toml ] || cd ../.. || exit 1
export PATH="$HOME/.local/bin:$PATH" PYTHONUTF8=1
if [ -x .venv/bin/python ]; then .venv/bin/python -m ytauto doctor; else echo "Primero ejecuta instalar.sh"; fi
