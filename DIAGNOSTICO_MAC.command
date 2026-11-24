#!/bin/bash
# Diagnostico de YTAUTO en Mac: que esta instalado y que falta.
cd "$(dirname "$0")" || exit 1
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
export PATH="$HOME/.local/bin:$PATH" PYTHONUTF8=1
if [ -x ".venv/bin/python" ]; then .venv/bin/python -m ytauto doctor; else echo; echo "  Primero ejecuta INSTALAR_MAC.command"; fi
echo; read -r -p "  Pulsa Intro para cerrar... " _
