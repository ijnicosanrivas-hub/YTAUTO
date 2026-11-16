# Motor audiovisual local (sin coste)

Adaptadores incluidos y dados de alta automáticamente en el primer arranque
(orden = prioridad dentro de cada categoría; el primero disponible responde):

| Categoría | Principal | Respaldo | Notas |
|---|---|---|---|
| rendering | `ffmpeg` | — | zoompan, xfade, ASS karaoke, loudnorm 2 pasadas, ducking |
| tts | `piper` (neuronal) | `espeak` | Piper necesita un modelo descargado; si no hay, se usa espeak-ng |
| image | `library_images` | `procedural_images` | La biblioteca usa tus imágenes con licencia; el procedural genera fondos abstractos |
| video | `library_videos` | — | Clips propios con licencia |
| music | `library_music` | `procedural_music` | Música sintetizada CC0 por estado de ánimo |
| sfx | `library_sfx` | `synth_sfx` | whoosh, impact, riser, pop, ambience, click |
| subtitle | `acoustic` | `proportional` | Frases alineadas a las pausas reales del audio (FFmpeg); respaldo proporcional |
| storage | `local_storage` | — | `data/storage` |

Los proveedores que no superan su `health_check` (p. ej. biblioteca vacía o Piper sin
modelos) se saltan automáticamente y se usa el siguiente de la cadena.

## Voz natural gratis con Piper
```bash
pip install piper-tts
python -m piper.download_voices es_ES-davefx-medium --data-dir data/models/piper
python -m ytauto providers test piper
```
Revisa la licencia de cada voz (MODEL_CARD) antes de un uso comercial.

## Biblioteca de recursos con licencia
```
library/
  images/  faro_noche.jpg  faro_noche.jpg.json
  videos/  olas.mp4        licenses.json
  music/   calma.mp3       calma.mp3.json
  sfx/     whoosh.wav      whoosh.wav.json
```
Fichero lateral `<fichero>.json`:
```json
{"license": "CC0", "attribution": "Autor", "url": "https://…", "tags": ["faro", "noche"], "commercial_use": true}
```
O un `licenses.json` por carpeta con `{"fichero.ext": {...}, "*": {...}}`.
**Los ficheros sin licencia declarada se ignoran.** Las etiquetas y el nombre del fichero
se comparan con la búsqueda de cada escena; se evitan imágenes repetidas (hash perceptual).

## Rendimiento orientativo
Vídeo de 60 s en CPU de 4 núcleos: ~4–5 min de principio a fin, de los cuales la mayor parte
es codificación H.264 (máster, previsualización y 3 exportaciones). Las escenas se cachean:
rehacer una escena solo vuelve a renderizar esa escena.

## Prueba de producción completa
```bash
python scripts/demo_production.py                 # sin Claude (borradores locales)
python scripts/demo_production.py --claude        # con Claude Code (consume la suscripción)
python -m pytest -m slow                          # E2E: MP4 45–75 s, 1080×1920, H.264/AAC, sincronía
```

## Calidad de vídeo corto (fase 6)
- **Guion**: la narración debe cubrir entre el 80 % y el 105 % de la duración (sin tiempos muertos
  ni textos que no caben); el guionista recibe el máximo de palabras por escena.
- **Voz ↔ escena**: cada escena se ajusta a su locución (nunca corta la voz, deja ≤ 0,8 s de aire).
  Si falta narración (> 3 s), la voz pide al guionista ampliar las escenas con más hueco; si no quedan
  rondas, alarga las escenas como último recurso. Margen de 0,3 s sobre el mínimo de 45 s.
- **Retención (medida con datos reales, 15 puntos del revisor)**: gancho ≤ 3 s, primera palabra
  ≤ 0,5 s, ningún hueco sin voz > 1,5 s, ningún plano sin cambio visual > 2,5/4/6 s (intensidad
  alta/media/baja).
- **Puntuación del revisor**: técnica 30 + sincronía 15 + retención 15 + editorial (Claude) 40.
  Fallos críticos (fotogramas negros, duración, resolución) impiden aprobar.
- **Movimientos**: slow_zoom_in, zoom_out, pan_left/right/up, tilt_down, ken_burns, punch_in, drift.
- **Subtítulos** (`subtitle_mode` del proyecto o del perfil de plataforma): `karaoke` (resaltado
  palabra a palabra), `word_pop` (una palabra grande con rebote), `line` (frase clásica).
