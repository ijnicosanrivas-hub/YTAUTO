#!/bin/bash
# YTAUTO en Linux: comprueba la instalacion y abre la fabrica en el navegador.
cd "$(dirname "$0")" || exit 1
[ -f pyproject.toml ] || cd ../.. || exit 1
export PATH="$HOME/.local/bin:$PATH" PYTHONUTF8=1
[ -x .venv/bin/python ] || { echo "Primero ejecuta instalar.sh"; exit 1; }
.venv/bin/python -m ytauto doctor || { echo "Arregla lo que indica arriba."; exit 1; }
exec .venv/bin/python -m ytauto.api.server --lan --open
