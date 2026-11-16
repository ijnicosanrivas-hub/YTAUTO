# CLAUDE.md — YTAUTO

Fábrica multiagente de vídeos cortos verticales (9:16, 45–75 s) para Reels, Shorts y TikTok.
Arquitectura: `docs/architecture.md`. Decisiones: `docs/adr/`.

## Reglas innegociables
1. `backend/ytauto/agents/` y `backend/ytauto/orchestrator/` **nunca** importan adaptadores
   concretos (`ytauto.providers.<categoría>.<proveedor>`) ni SDKs de proveedores. Solo
   `ytauto.providers.interfaces`. Lo verifica `tests/test_architecture.py`.
2. La inteligencia de Claude se usa solo a través de `LLMProvider`. En producción es
   `ClaudeCodeCLIProvider` (binario oficial `claude -p`, sesión Pro). Nunca la API de Anthropic
   asumida como incluida en Pro, nunca extraer tokens, nunca instancias paralelas para eludir límites.
3. Ningún gasto (proveedor `is_paid`) ni publicación sin autorización expresa registrada.
4. Nunca guardar claves en el repositorio. Credenciales cifradas fuera de git (`data/`).
5. No declarar nada terminado sin pruebas que lo demuestren.

## Comandos
- Pruebas: `python -m pytest -q` (desde la raíz). Las de Claude real: `python -m pytest -m claude`.
- CLI: `python -m ytauto --help` (`--offline --mock-providers` para pruebas sin Claude).
- Estilo: Python 3.11+, pydantic v2, tipado; textos de usuario en español.

## Estructura
- `backend/ytauto/core` dominio (modelos, narrativa, espacio de trabajo, eventos, plataformas).
- `backend/ytauto/llm` motor LLM (CLI de Claude Code, simulados).
- `backend/ytauto/agents` los 9 agentes. Cada agente con Claude define esquema + criterios de aceptación.
- `backend/ytauto/db` SQLite (esquema, `SqlStateStore`, backups); `backend/ytauto/queue` cola y worker.
- `backend/ytauto/orchestrator` flujo de 18 fases (DAG), estados, aprobaciones, correcciones.
- `backend/ytauto/providers/interfaces` contratos; adaptadores en subcarpetas por categoría.
- `.claude/agents/*.md` instrucciones de rol de cada agente (usadas por `claude -p --agent`).
- `config/` modelos por agente, narrativa, perfiles de plataforma.

## Modelos
Implementación diaria con Sonnet; Opus solo para decisiones de arquitectura o errores complejos.
En `config/models/models.yaml` usar alias (`sonnet`, `opus`, `haiku`), no versiones fijas.
