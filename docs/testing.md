# Pruebas

```bash
make test        # rápidas: backend + frontend, sin Claude ni costes (≈2 min)
make test-all    # + producciones reales con FFmpeg y espeak-ng (varios minutos)
make claude-smoke  # UNA llamada real a Claude Code (consume un poco de cuota)
make coverage    # cobertura (≈92 % del backend)
make lint        # ruff: código muerto, nombres sin definir
```

Marcadores de `pytest`: `slow` (renderizado real), `claude` (usa tu sesión de Claude Code). Por defecto
se omiten los dos.

## Qué cubre cada requisito
| Requisito | Dónde se prueba |
|---|---|
| Los nueve agentes (esquema, criterios de aceptación, reintentos) | `test_agents.py`, `test_short_form.py` |
| Orquestador (flujo de 18 fases, aprobaciones, correcciones, mejora automática acotada, pausa/reanudación) | `test_orchestrator.py` (con memoria **y** SQLite) |
| Dependencias entre fases | `test_orchestrator.py` (`downstream`, invalidaciones) |
| Cola de tareas (idempotencia, concurrencia, leases, pausa por límite) | `test_queue.py`, `test_worker.py` |
| Persistencia y copias de seguridad | `test_persistence.py` |
| Recuperación tras caídas | `test_worker.py`, `test_orchestrator.py` |
| Proveedores y contrato de cada adaptador | `test_registry.py` (contrato de todos), `test_integrations.py` |
| Cambio de proveedor sin tocar agentes | `test_provider_swap.py`, `test_architecture.py` |
| Fallback y rutas de error del gasto | `test_provider_swap.py`, `test_gateway_paths.py` |
| Credenciales (cifrado, enmascarado, clave maestra) | `test_registry.py`, `test_integrations.py` |
| Presupuestos y autorización de gasto | `test_provider_swap.py`, `test_integrations.py` |
| Renderizado con FFmpeg, mezcla y normalización | `test_media.py` |
| Sincronización voz/imagen/subtítulos | `test_media.py`, `test_short_form.py` |
| Exportación vertical y adaptación a plataformas | `test_platforms.py` |
| Autorización de publicación | `test_orchestrator.py`, `test_integrations.py`, `test_api.py` |
| Compatibilidad con Windows (rutas con espacios/`:`/tildes, fuentes, codificación, `.env` con BOM) | `test_windows_compat.py` |
| Instalador y scripts de Windows (revisión estática: sin PowerShell, esperas, saltos, interfaz incluida) | `test_installer.py` |
| Herramientas locales (`tools/`, Git Bash, PATH) | `test_tools.py` |
| API REST y WebSocket | `test_api.py` |
| Uso en la nube sin instalar (configuración de Codespaces, arranque idempotente) | `test_codespaces.py` |
| Acceso desde el móvil (código de acceso, enlaces, servidor real en modo `--lan`) | `test_lan.py`, `frontend/src/logic.test.ts` |
| Tema de personajes (validez, API, prompts de rol coherentes) | `test_theme.py` |
| Interfaz (lógica) | `frontend/src/logic.test.ts` |
| Ladrillos a escala real (taco, placas, muro, mosaico) y efectos | `frontend/src/minifig/bricks.test.ts` |
| Hub de la Batcueva (instalaciones, cámara de zoom, últimas acciones) y expediente del agente | `frontend/src/minifig/hub.test.ts`, `frontend/src/components/AgentPanel.test.tsx` |
| Minifiguras: una plantilla para los nueve, rasgos conservados, animaciones por estado real | `frontend/src/minifig/minifig.test.ts` |
| Producción real completa (MP4 45–75 s, 1080×1920, H.264/AAC, sincronizado) | `test_media.py::test_full_local_production…` y `test_platforms.py::test_real_production…` (`-m slow`) |
| Integración con el binario de Claude Code | `test_claude_cli.py` (simulado) y `test_real_claude_smoke` (`-m claude`) |

## Cómo se garantiza que las pruebas sirven
Las pruebas de seguridad se comprueban con **mutaciones**: se rompe el código a propósito y se verifica que
la prueba falla (no publicar sin autorización, no duplicar publicaciones, liberar la reserva de coste si un
proveedor de pago falla, respetar el margen de pico del AAC, usar las líneas de subtítulo del guion…).
Dos pruebas que pasaban sin detectar nada se reescribieron por este motivo.

## Qué NO está probado
- **Servicios externos reales**: YouTube, Instagram, TikTok, ElevenLabs y OpenAI se prueban solo contra
  servidores HTTP simulados (`test_integrations.py`). Ninguno contra una cuenta real.
- **Voz Piper real**: no hay modelo descargado en este entorno; se prueba con una voz simulada que respeta su API.
- **Windows real**: lo anterior solo reproduce en Linux lo que suele fallar en Windows. Los `.bat` no se han
  ejecutado nunca en un Windows (las descargas y el instalador de Claude Code tampoco).
- **Navegadores distintos de Chromium** y dispositivos móviles reales (solo una ventana de 390 px).
- **Rendimiento con muchos proyectos simultáneos** y bases de datos grandes.
