# Tema de personajes: Gotham

Los nueve agentes tienen personalidad de personajes de Gotham City. Es un **tema**: una capa
intercambiable que solo cambia la presentación. Uso personal, no distribuible.

| Agente | Personaje | Bando |
|---|---|---|
| Jefe | **Batman** (Bruce Wayne) | héroe |
| Director | **El Acertijo** | villano |
| Guionista | **El Joker** | villano |
| Recursos | **Catwoman** | antiheroína |
| Voz | **Bane** | villano |
| Editor | **Nightwing** | héroe |
| Sonido | **El Pingüino** | villano |
| Revisor | **Dos Caras** | villano |
| Publicador | **Harley Quinn** | antiheroína |

## Qué cambia
- **Interfaz**: la sala es una Batcueva 3D y los nueve agentes son **minifiguras LEGO Batman** con una
  estética única (ver `docs/style_bible.md`); cada agente tiene su color, glifo, apodo y frase; la página *Agentes* muestra fichas de personaje; paleta negra y amarilla.
- **Frases**: salen del estado **real** del agente (en ejecución, esperando, error, terminó). No hay actividad
  inventada: si no pasa nada, el personaje está «en espera».
- **Anillo de estado**: la figura y su placa llevan el color del personaje y un anillo lleva el color del **estado**
  (en espera / ejecución / esperando / error), para que el estado siga leyéndose igual.
- **Prompts de rol** (`.claude/agents/*.md`): un párrafo de personalidad que solo afecta al **tono de los campos
  explicativos** (resúmenes, motivos, notas).

## Qué NO cambia
- El **contenido de los vídeos** (guion, narración, subtítulos, prompts de imagen, textos de publicación),
  el esquema JSON de cada agente, el flujo de 20 fases, las autorizaciones de gasto y publicación.
  Un guion de pulpos no habla de Gotham.

## Cambiar de tema
```bash
# En .env:  YTAUTO_THEME=classic      (por defecto: gotham)
python scripts/aplicar_tema.py --theme classic   # quita el párrafo de personalidad de los prompts
python scripts/aplicar_tema.py --theme gotham    # lo vuelve a poner
python scripts/aplicar_tema.py --check           # comprueba que los prompts coinciden con el tema
```
La interfaz toma el tema de `YTAUTO_THEME` (reinicia el servidor). Los prompts se regeneran con el script
(una prueba comprueba que no queden desactualizados). Para crear otro universo, copia
`config/theme/gotham.yaml` a `config/theme/<nombre>.yaml`, cambia los nueve personajes y usa `YTAUTO_THEME=<nombre>`.
Un tema roto o inexistente vuelve a `classic` sin romper la aplicación.

## Nota de originalidad
Las frases son **originales** (no citan diálogos de cómics, películas ni series); los glifos son emoji estándar.
No se incluyen logotipos ni imágenes de terceros.
