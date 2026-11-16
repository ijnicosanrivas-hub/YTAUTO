# YTAUTO — Fábrica multiagente de vídeos cortos

Plataforma que convierte una temática en un vídeo vertical (1080×1920, H.264/AAC, 45–75 s)
listo para **Instagram Reels, YouTube Shorts y TikTok**, mediante nueve agentes coordinados
por un agente jefe, una única licencia **Claude Pro** (vía Claude Code) y proveedores
audiovisuales intercambiables.

> Estado: en desarrollo por fases. Ver la tabla de progreso más abajo.

## Agentes
| # | Agente | Claude | Función |
|---|---|---|---|
| 1 | Jefe | no (determinista) | Coordina el flujo, correcciones, presupuesto e informe |
| 2 | Director | sí | Concepto, estilo, estructura narrativa, escenas y ritmo |
| 3 | Guionista | sí | Gancho, narración ajustada a la duración, subtítulos |
| 4 | Recursos | sí (prompts) | Prompts, búsqueda/generación, coherencia, licencias |
| 5 | Voz | opcional | Locución por escena, ritmo, sincronización |
| 6 | Editor | no | Montaje por escenas, movimiento, transiciones, render |
| 7 | Sonido | no | Música, efectos, ducking, normalización |
| 8 | Revisor | sí + técnico | Puntuación 0–100 (no predice viralidad) y correcciones |
| 9 | Publicador | sí (haiku) | Exportaciones, metadatos, miniaturas, publicación autorizada |

## Requisitos
- Python 3.11+, FFmpeg 6+ (con libass), Node 20+ (interfaz).
- Claude Code instalado y con sesión iniciada: `claude /login` (cuenta Pro).

## Puesta en marcha (desarrollo)
```bash
pip install -e ".[dev]"
cp .env.example .env   # y genera YTAUTO_MASTER_KEY
python -m pytest -q
```

## Interfaz
```bash
cd frontend && npm install && npm run build && cd ..
python -m ytauto.api.server        # http://127.0.0.1:8000  (añade --offline para probar sin Claude)
```

## Uso por línea de comandos
```bash
python -m ytauto new --name "Pulpos" --topic "curiosidades de los pulpos" --duration 60
python -m ytauto run --forever          # worker (cola de producción)
python -m ytauto status <project_id>
python -m ytauto approve <project_id> script_approval
python -m ytauto queue                  # carriles, pausas por límite de uso
python -m ytauto resume-claude          # tras un límite de uso o `claude /login`
python -m ytauto backup
```
`--offline --mock-providers` permite probar el flujo completo sin Claude ni proveedores.

## Progreso
| Fase | Contenido | Estado |
|---|---|---|
| 1 | Análisis y arquitectura | ✅ `docs/` |
| 2 | Motor multiagente | ✅ agentes, orquestador, capa Claude |
| 3 | Cola, memoria y persistencia | ✅ SQLite, cola por carriles, worker, backups |
| 4 | Sistema modular de proveedores | ✅ registro, credenciales cifradas, fallback, presupuesto — ver `docs/providers.md` |
| 5 | Motor audiovisual local | ✅ FFmpeg, Piper/espeak, procedural, biblioteca — ver `docs/local_engine.md` |
| 6 | Vídeos cortos y montaje | ✅ retención medida, voz↔escena, subtítulos acústicos y 3 estilos |
| 7 | Interfaz y sala de producción | ✅ FastAPI + WebSocket + React/R3F — ver `docs/ui.md` |
| 8 | Exportación multiplataforma | ⏳ (perfiles provisionales) |
| 9 | Integraciones externas | ⏳ |
| 10 | Pruebas completas y documentación | ⏳ |

## Costes
La licencia Claude Pro cubre solo el uso de Claude dentro de la suscripción. Los proveedores
audiovisuales externos se facturan aparte y **nunca** se usan sin presupuesto y autorización.
Por defecto todo funciona con herramientas locales y gratuitas.
