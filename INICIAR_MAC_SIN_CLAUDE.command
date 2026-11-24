#!/bin/bash
# YTAUTO (modo de prueba, sin Claude) — doble clic en el Finder. Comprueba la instalacion y abre la fabrica en el navegador.
cd "$(dirname "$0")" || exit 1
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
export PATH="$HOME/.local/bin:$PATH" PYTHONUTF8=1
if [ ! -x ".venv/bin/python" ]; then
  echo; echo "  Primero ejecuta INSTALAR_MAC.command"; echo
  read -r -p "  Pulsa Intro para cerrar... " _; exit 1
fi
if ! .venv/bin/python -m ytauto doctor --no-claude; then
  echo; echo "  Arregla lo que indica arriba y vuelve a abrir este archivo."; echo
  read -r -p "  Pulsa Intro para cerrar... " _; exit 1
fi
echo; echo "  YTAUTO esta funcionando. Deja esta ventana abierta mientras lo uses (cierrala para apagarlo)."
exec .venv/bin/python -m ytauto.api.server --offline --open
