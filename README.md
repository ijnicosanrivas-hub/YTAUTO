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

## Progreso
| Fase | Contenido | Estado |
|---|---|---|
| 1 | Análisis y arquitectura | ✅ `docs/` |
| 2 | Motor multiagente | ✅ agentes, orquestador, capa Claude |
| 3 | Cola, memoria y persistencia | ⏳ |
| 4 | Sistema modular de proveedores | ⏳ (interfaces ya definidas) |
| 5 | Motor audiovisual local | ⏳ |
| 6 | Vídeos cortos y montaje | ⏳ |
| 7 | Interfaz y sala de producción | ⏳ |
| 8 | Exportación multiplataforma | ⏳ (perfiles provisionales) |
| 9 | Integraciones externas | ⏳ |
| 10 | Pruebas completas y documentación | ⏳ |

## Costes
La licencia Claude Pro cubre solo el uso de Claude dentro de la suscripción. Los proveedores
audiovisuales externos se facturan aparte y **nunca** se usan sin presupuesto y autorización.
Por defecto todo funciona con herramientas locales y gratuitas.
