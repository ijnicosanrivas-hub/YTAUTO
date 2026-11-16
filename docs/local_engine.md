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
| subtitle | `proportional` | — | Alineación por longitud de palabra sobre la duración real de la voz |
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
