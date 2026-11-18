# Pasar YTAUTO a otras personas

Cualquiera con Windows 10/11 puede instalarlo **con un solo archivo**, sin instalar nada antes.

## Qué les mandas
- **El enlace de descarga** (el más fácil, siempre trae la última versión):
  `https://github.com/ijnicosanrivas-hub/ytauto/archive/refs/heads/claude/multiagent-audiovisual-system-hv0bwv.zip`
  (funciona si el repositorio es público; si es privado, quien lo reciba necesita acceso a él).
- **O el ZIP** que tú ya descargaste: envíalo por correo, WhatsApp o una nube.
- Y este mensaje:

> 1. Extrae el ZIP (clic derecho → *Extraer todo*) en una carpeta como `C:\YTAUTO`.
> 2. Abre `INSTALAR_WINDOWS.bat` (doble clic). Si Windows avisa, *Más información → Ejecutar de todos modos*.
> 3. Espera de 10 a 30 minutos y, al final, inicia sesión en Claude con **tu propia cuenta de Claude Pro**.
> 4. Para usarlo: icono **YTAUTO** del Escritorio.

Dentro del ZIP hay un `LEEME_PRIMERO.txt` con estos mismos pasos.

## Qué necesita cada persona
- Windows 10 (versión 1803+) o Windows 11, Internet y 10 GB libres.
- **Su propia cuenta de Claude Pro.** El programa usa la sesión de Claude Code de cada usuario: **no compartas tu cuenta**
  ni tu sesión; sus videos gastarían tu cuota.
- No necesita ser administrador ni instalar Python, Node ni nada: el instalador lo hace todo.

## Antes de pasarlo (léelo)
- **Nada de lo tuyo viaja en el ZIP**: tus proyectos (`projects`), datos (`data`), claves y `.env` están fuera del repositorio.
  Si pasas un ZIP hecho a mano desde tu carpeta de trabajo, **no incluyas** `data`, `projects`, `library`, `.env` ni `tools`.
- **Tema Gotham / LEGO:** el programa trae por defecto el tema de personajes de Gotham y las figuras tipo LEGO, que
  indicaste que son un trabajo **personal y no distribuible** (marcas de terceros). Si lo vas a repartir, es más prudente
  entregarlo con el diseño neutro: en el `.env` de cada persona (o en `.env.example` antes de pasarlo) pon
  `YTAUTO_THEME=classic` y ejecuta `python scripts/aplicar_tema.py --theme classic`.
- Tampoco se incluyen imágenes, vídeos ni música de terceros: cada uno usa su biblioteca con licencia (`library\`).

## Qué instala (y cómo quitarlo)
Python y Git en la cuenta del usuario; FFmpeg y la voz **dentro de la carpeta** (`tools\`); Claude Code en
`%USERPROFILE%\.local\bin`. Para quitarlo: borrar la carpeta y el icono del Escritorio; el resto, desde
*Configuración → Aplicaciones*. Detalles en `docs/WINDOWS.md`.

## Qué está comprobado
La instalación desde un ZIP limpio funciona en Linux (sin Node: la interfaz ya viene compilada). El `.bat` de Windows
**no se ha ejecutado en un Windows real**; pide a la primera persona que lo pruebe y te cuente si algún paso falla.
