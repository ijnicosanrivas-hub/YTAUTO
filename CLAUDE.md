# CLAUDE.md — YTAUTO

Fábrica multiagente de vídeos cortos verticales (9:16, 45–75 s) para Reels, Shorts y TikTok.
Arquitectura: `docs/architecture.md`. Decisiones: `docs/adr/`.

## Reglas innegociables
1. `backend/ytauto/agents/` y `backend/ytauto/orchestrator/` **nunca** importan adaptadores
   concretos (`ytauto.providers.<categoría>.<proveedor>`) ni SDKs de proveedores. Solo
   `ytauto.providers.interfaces`. Lo verifica `tests/test_architecture.py`.
2. La inteligencia de Claude se usa solo a través de `LLMProvider`. En producción es `LicenseRouter`
   → `ClaudeCodeCLIProvider` (binario oficial `claude -p`) con la licencia del canal: su sesión
   (`CLAUDE_CONFIG_DIR`) o su clave de API cifrada. Nunca la API asumida como incluida en Pro, nunca extraer
   tokens, nunca dos llamadas a la vez con la misma licencia, nunca saltar solo a la licencia de otro canal.
3. Ningún gasto (proveedor `is_paid`) ni publicación sin autorización expresa registrada. Privado y público son
   autorizaciones distintas (`publish:<plataforma>` / `publish:<plataforma>:public`); nunca se publica en abierto por defecto.
   Los adaptadores `requires_network` no se registran solos, no se prueban contra el servicio real y los de pago
   necesitan precio configurado.
4. Nunca guardar claves en el repositorio. Credenciales cifradas fuera de git (`data/`).
5. No declarar nada terminado sin pruebas que lo demuestren.

## Comandos
- Pruebas: `python -m pytest -q` (desde la raíz). Producción real E2E: `python -m pytest -m slow`. Claude real: `python -m pytest -m claude`.
- Demo: `python scripts/demo_production.py [--claude]`.
- Interfaz: `python -m ytauto.api.server [--offline]`; frontend en `frontend/` (`npm run build|dev|test`).
- CLI: `python -m ytauto --help` (`--offline --mock-providers` para pruebas sin Claude).
- Estilo: Python 3.11+, pydantic v2, tipado; textos de usuario en español.

## Estructura
- `backend/ytauto/core` dominio (modelos, narrativa, espacio de trabajo, eventos, plataformas).
- `backend/ytauto/llm` motor LLM (CLI de Claude Code, simulados).
- `backend/ytauto/agents` los 9 agentes. Cada agente con Claude define esquema + criterios de aceptación.
  Director = estratega viral (3 ganchos, ángulo, retención, CTA, títulos, portada); el usuario decide concepto,
  guion y storyboard antes de gastar (`OPTIONAL_GATES` en `orchestrator/pipeline.py`).
- `backend/ytauto/db` SQLite (esquema, `SqlStateStore`, backups); `backend/ytauto/queue` cola y worker.
- `backend/ytauto/api` FastAPI + WebSocket (`server.py`) y estado en vivo de agentes (`board.py`).
- `frontend/` React + TypeScript + React Three Fiber (sala 3D en `src/pages/ProductionRoom.tsx`).
- `backend/ytauto/orchestrator` flujo de 20 fases (DAG), estados, aprobaciones, correcciones.
- `backend/ytauto/providers/interfaces` contratos; adaptadores en subcarpetas por categoría.
- `.claude/agents/*.md` instrucciones de rol de cada agente (usadas por `claude -p --agent`).
- `instaladores/<windows|mac|linux|movil|web>/` lanzadores e instaladores por sistema (encuentran solos la raíz). Windows: `INSTALAR_WINDOWS.bat` en cmd puro (sin PowerShell); `backend/ytauto/core/tools.py` localiza FFmpeg/voz/Claude/Git Bash instalados; `frontend/dist` se versiona (el paquete no exige Node).
- `config/theme/` tema de personajes (`YTAUTO_THEME`, por defecto `gotham`); `scripts/aplicar_tema.py` sincroniza los prompts de rol. Solo presentación.
- Paquetes: `scripts/empaquetar.py` (un ZIP por sistema con su instalador arriba y su lista de archivos) y `.github/workflows/publicar.yml` (pruebas + Releases en cada push a main).
  `scripts/instalar.py` instala todo en un equipo nuevo o ACTUALIZA en su sitio la instalación existente (solo archivos
  cambiados; nunca toca `data/`, `library/`, `projects/`, `tools/`, `.venv`, `.env`; dependencias solo si cambian).
- Canales: `config/channels.yaml` (4 canales, cada uno con su perfil) · licencias `backend/ytauto/llm/licenses.py` ·
  entrevista del director `agents/briefing.py` · API `api/channels_api.py` · detalle en `docs/canales.md`.
- Cuentas conectadas: ElevenLabs (clave cifrada + saldo real) y Higgsfield (CLI oficial con los créditos del plan;
  la API es otro saldo) · `api/accounts_api.py` · `providers/higgsfield.py` · detalle en `docs/cuentas.md`.
  ElevenLabs: voz (v4 con emoción, diálogos, tiempos por palabra, Voice Changer) y, si se elige, efectos IA; el usuario
  decide qué usar en un cuestionario (`core/audio_features.py`). Nunca música. Música elegible por vídeo: Biblioteca de audio de YouTube Studio (importada a mano, sin API)
  · `providers/music/youtube_audio_library.py` · `api/music_api.py`.
- `config/` modelos por agente, narrativa, perfiles de plataforma (con `verified_at`, `sources` y `unverified`: no presentar como oficial lo que no lo es).

## Modelos
Implementación diaria con Sonnet; Opus solo para decisiones de arquitectura o errores complejos.
En `config/models/models.yaml` usar alias (`sonnet`, `opus`, `haiku`), no versiones fijas.
