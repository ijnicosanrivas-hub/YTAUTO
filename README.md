# YTAUTO — Fábrica multiagente de vídeos cortos

Convierte una temática en un vídeo vertical (**1080×1920, H.264/AAC, 45–75 s**) listo para
**Instagram Reels, YouTube Shorts y TikTok**, con nueve agentes coordinados por un agente jefe.
La inteligencia es **una única licencia Claude Pro** (a través de Claude Code, sin API) y todo lo
audiovisual funciona **en local y gratis** por defecto; los proveedores externos son opcionales e intercambiables.

## Qué hace
`temática → dirección creativa → guion (con tu aprobación) → recursos → locución → montaje → música y efectos →
render → revisión independiente (0–100) → correcciones → aprobación final → exportación por plataforma →
paquete de publicación → publicación solo con tu autorización → informe`

| # | Agente | Usa Claude | Función |
|---|---|---|---|
| 1 | Jefe | no | Coordina las 18 fases, correcciones, presupuesto e informe |
| 2 | Director | sí | Concepto, estilo, estructura de retención, escenas y ritmo |
| 3 | Guionista | sí | Gancho, narración ajustada a la duración, líneas de subtítulo |
| 4 | Recursos | sí (prompts) | Prompts, búsqueda/generación, coherencia, licencias |
| 5 | Voz | opcional | Locución por escena, ritmo, subtítulos alineados al audio |
| 6 | Editor | no | Montaje por escenas, cámara, transiciones, render |
| 7 | Sonido | no | Música, efectos, ducking, −14 LUFS, margen de pico |
| 8 | Revisor | sí + medidas | Nota 0–100 (**no predice viralidad**) y correcciones dirigidas |
| 9 | Publicador | sí (haiku) | Exportaciones validadas, textos por plataforma, publicación autorizada |

## Tema Gotham
Los agentes son personajes de Gotham (Batman es el jefe; el Joker, el guionista…) y la sala es *La Baticueva*.
Es solo presentación: no cambia el contenido de los vídeos. Detalles y cómo volver al estilo clásico en `docs/theme.md`.

## ¿Usas Windows y no sabes de informática?
Sigue la **[guía paso a paso para Windows](docs/WINDOWS.md)**: descargas el ZIP, haces doble clic en
`INSTALAR_WINDOWS.bat`, inicias sesión en Claude una vez y abres `INICIAR_WINDOWS.bat`. `DIAGNOSTICO_WINDOWS.bat`
(o `python -m ytauto doctor`) dice qué falta y cómo arreglarlo.

## Requisitos
- **Python 3.11+**, **FFmpeg 6+** (con `libass`), **espeak-ng** (voz local de respaldo), **Node 20+** (interfaz).
- **Claude Code** instalado y con sesión iniciada (`claude /login`, cuenta Pro).
- Linux, macOS o **Windows 10/11** (ver la guía de Windows; sin WSL).

```bash
# Debian/Ubuntu
sudo apt install ffmpeg espeak-ng
```

## Instalación
```bash
git clone <este-repositorio> && cd YTAUTO
python3 -m venv .venv && source .venv/bin/activate
make install            # pip install -e ".[dev]" + npm install
make ui                 # compila la interfaz (una vez)
cp .env.example .env    # opcional: ajusta rutas, concurrencia, token…
make test               # comprueba que todo funciona (≈2 min, sin Claude ni costes)
```
Instala **desde el repositorio** (modo editable): la configuración (`config/`) se localiza respecto a él.

## Primer vídeo
```bash
claude /login           # una vez, con tu cuenta Pro
make run                # http://127.0.0.1:8000  (o `make run-offline` para probar sin Claude)
```
En la interfaz: **Proyectos → Nuevo vídeo** → escribe la temática (modo *Automático*: el director decide el resto)
→ aprueba el guion → mira el vídeo → aprueba → elige qué exportar o publicar.
Por línea de comandos: `python -m ytauto new --name "Pulpos" --topic "curiosidades de los pulpos" --duration 60`
y `python -m ytauto run --forever` (más órdenes en `python -m ytauto --help`).

Una producción de prueba sin Claude: `make demo` · con Claude real: `python scripts/demo_production.py --claude`.

## Consumo de Claude (una sola licencia Pro)
- **Una tarea de Claude a la vez** por defecto (máximo 2). Más concurrencia no aumenta tu cuota, solo la agota antes.
- Si la nota del revisor es apta pero marca incidencias **graves** de guion o recursos, se aplica **una** ronda de
  mejora (unas llamadas más; `YTAUTO_FIX_MAJOR_ISSUES=0` la desactiva). Un guion que aprobaste tú no se reescribe solo.
- Se guarda cada resultado y se reutiliza: reanudar o rehacer una escena **no repite** llamadas ya hechas.
- Si Claude Code avisa de un límite de uso o de sesión no iniciada, **solo se pausa el carril de Claude** (lo local
  sigue) y se reanuda solo (si se conoce la hora) o con `python -m ytauto resume-claude`.
- **Medido en dos producciones reales** (45 s, Sonnet para el trabajo creativo y Haiku para los textos de publicación):
  **6 y 7 llamadas, ≈165–170 s de Claude y ≈27 000 tokens de salida en cada una** (el director y a veces el guionista
  necesitan un reintento). Son cifras **indicativas** de solo dos ejecuciones; Claude Pro no factura por uso y tus
  límites dependen de tu plan. Cada llamada queda registrada en el panel «Modelos Claude».

## Coste de los proveedores externos
Por defecto **0 €**: FFmpeg, espeak-ng (o Piper), imágenes procedurales o de tu biblioteca, música y efectos
sintetizados. Los proveedores de pago (ElevenLabs, OpenAI Images…) y las publicaciones oficiales son opcionales,
están **desactivados** y exigen credenciales, presupuesto y autorización: ver `docs/integrations.md`.

## Mejorar la calidad sin gastar
- **Voz natural gratis**: `pip install piper-tts` y descarga un modelo (`docs/local_engine.md`).
- **Imágenes reales**: coloca imágenes, clips, música y efectos **con licencia** en `library/` (los ficheros sin
  licencia declarada se ignoran). Sin biblioteca, las imágenes son fondos abstractos.

## Seguridad
- Credenciales **cifradas** (Fernet), clave maestra fuera de git; nunca se muestran completas ni salen en logs.
- Servidor solo en `127.0.0.1`; fuera de ahí exige `YTAUTO_API_TOKEN`.
- **Nada se publica ni se gasta sin autorización expresa.** Privado y público son decisiones distintas y nunca se
  publica en abierto por defecto.
- Copias de seguridad: `make backup` (base de datos, configuración y JSON de proyectos; rotación de 10).

## Documentación
| | |
|---|---|
| `docs/WINDOWS.md` | **Instalación en Windows paso a paso** |
| `docs/NUBE.md` | **Usarlo sin instalar nada en tu PC** (GitHub Codespaces; enlace de un toque) |
| `docs/MOVIL.md` | **Usarlo desde el iPhone** (mismo Wi-Fi, con `INICIAR_WINDOWS_MOVIL.bat`) |
| `docs/architecture.md` | Arquitectura, capas y flujo de 18 fases |
| `docs/providers.md` | Proveedores intercambiables: escribir un adaptador, sustituir uno, fallback y presupuesto |
| `docs/local_engine.md` | Motor local, biblioteca con licencias, calidad de vídeo corto |
| `docs/platforms.md` | Requisitos verificados de Reels/Shorts/TikTok y qué **no** está verificado |
| `docs/integrations.md` | Publicación oficial y proveedores de pago; qué falta para usarlos en real |
| `docs/ui.md` | Interfaz y sala de producción |
| `docs/lego_research.md` | Investigación LEGO: medidas reales, colores, tipografía, qué no se pudo confirmar |
| `docs/style_bible.md` | Guía visual: minifiguras LEGO Batman y Batcueva 3D |
| `docs/theme.md` | Tema de personajes de Gotham (Batman, Joker…) y cómo cambiarlo |
| `docs/testing.md` | Pruebas, cobertura y qué no está probado |
| `docs/adr/` | Decisiones de arquitectura |

## Solución de problemas
| Síntoma | Causa / solución |
|---|---|
| «Claude Code no autenticado» | `claude /login`, luego `python -m ytauto resume-claude` (o «Reanudar ahora» en *Modelos Claude*) |
| El carril de Claude queda en pausa | Límite de uso de tu plan: espera a la hora indicada o reanuda manualmente |
| `FFmpeg no está instalado` / sin filtros | Instala FFmpeg 6+ con `libass`; `ffmpeg -filters` debe listar `ass`, `xfade`, `loudnorm` |
| La voz suena robótica | Es espeak-ng; instala un modelo Piper |
| Las imágenes son manchas abstractas | Añade tu biblioteca con licencia en `library/images` |
| «No se puede descifrar la credencial» | Cambió la clave maestra (`YTAUTO_MASTER_KEY` / `data/secrets/master.key`): restaura la anterior y vuelve a introducir las credenciales |
| La interfaz no carga | Falta `make ui` (el servidor sirve `frontend/dist`) |
| Una fase queda en *Bloqueada* | Lee el motivo en la ficha del proyecto; tras arreglarlo pulsa «Reintentar» |

## Estado y limitaciones
Las 10 fases del plan están implementadas y probadas (ver `docs/testing.md`). Lo que **no** he podido comprobar:
- **Publicación real** en YouTube, Instagram y TikTok y los proveedores de pago: solo contra servidores simulados.
  No hay flujo OAuth integrado (aportas tú los tokens) y TikTok exige una auditoría para publicar en abierto.
- **Márgenes de seguridad** de subtítulos: las plataformas no los publican; están marcados como no verificados.
- **Calidad visual**: sin tu biblioteca o un proveedor de imágenes, los fondos son abstractos.
- **Rendimiento**: ≈4–5 min por vídeo de 60 s en 4 núcleos; no probado con muchos proyectos a la vez.
- La puntuación del revisor es una nota interna de calidad, **no una predicción de rendimiento**.
