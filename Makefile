.PHONY: install ui test test-all claude-smoke run run-offline demo lint coverage backup

PY ?= python3

install:            ## Dependencias de Python (modo editable) y de la interfaz
	$(PY) -m pip install -e ".[dev]"
	cd frontend && npm install

ui:                 ## Compila la interfaz (necesario una vez antes de `make run`)
	cd frontend && npm run build

test:               ## Pruebas rápidas del backend y del frontend (sin Claude, sin costes)
	$(PY) -m pytest -q
	cd frontend && npx vitest run && npx tsc --noEmit

test-all:           ## Incluye las producciones reales con FFmpeg (varios minutos)
	$(PY) -m pytest -q -m "slow and not claude"

claude-smoke:       ## UNA llamada real a Claude Code (consume un poco de tu cuota)
	$(PY) -m pytest -q -m claude

run:                ## Sala de producción en http://127.0.0.1:8000 con Claude Code
	$(PY) -m ytauto.api.server

run-offline:        ## Igual, pero sin Claude (borradores locales, para probar)
	$(PY) -m ytauto.api.server --offline

demo:               ## Producción de prueba completa y local (sin Claude)
	$(PY) scripts/demo_production.py

lint:
	ruff check backend --select F,E9

coverage:
	$(PY) -m pytest -q --cov=backend/ytauto --cov-report=term-missing:skip-covered

backup:
	$(PY) -m ytauto backup
