#!/bin/bash
# YTAUTO con acceso desde el iPad o el iPhone (mismo Wi-Fi). Doble clic en el Finder.
cd "$(dirname "$0")" || exit 1
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
export PATH="$HOME/.local/bin:$PATH" PYTHONUTF8=1
if [ ! -x ".venv/bin/python" ]; then
  echo; echo "  Primero ejecuta INSTALAR_MAC.command"; echo
  read -r -p "  Pulsa Intro para cerrar... " _; exit 1
fi
if ! .venv/bin/python -m ytauto doctor; then
  echo; echo "  Arregla lo que indica arriba y vuelve a abrir este archivo."; echo
  read -r -p "  Pulsa Intro para cerrar... " _; exit 1
fi
echo
echo "  Modo MOVIL: la fabrica queda accesible desde tu iPad o iPhone conectados al mismo Wi-Fi."
echo "  Abajo aparece el enlace (con su codigo de acceso) que tienes que abrir en Safari."
echo "  Si el Mac pregunta si permites conexiones entrantes a Python, pulsa Permitir."
echo "  Deja esta ventana abierta mientras lo uses (cierrala para apagarlo)."
exec .venv/bin/python -m ytauto.api.server --lan --open
