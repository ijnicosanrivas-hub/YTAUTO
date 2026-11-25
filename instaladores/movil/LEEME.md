# YTAUTO en Android, iPhone y iPad

Los móviles y tabletas **no pueden ejecutar la fábrica**: necesita Python, FFmpeg y Claude Code, que Android e iPadOS
no permiten instalar (Claude Code no tiene versión oficial para Android). Lo que sí hacen es **manejarla entera como
una app** mientras un ordenador (Windows, Mac o Linux) la ejecuta en el mismo Wi-Fi.

## 1. En el ordenador
Abre el lanzador de modo móvil y deja la ventana abierta:

| Ordenador | Archivo |
| --- | --- |
| Windows | `INICIAR_WINDOWS_MOVIL.bat` |
| Mac | `INICIAR_MAC_MOVIL.command` |
| Linux | `bash iniciar_movil.sh` |

Aparece un enlace del tipo `http://192.168.1.20:8000/?token=…` (lleva un código de acceso). Si el sistema pregunta por
conexiones entrantes, pulsa **Permitir**.

## 2. En el móvil o la tableta
Abre ese enlace y añádelo como app:

| Dispositivo | Navegador | Cómo «instalarla» |
| --- | --- | --- |
| Android | Chrome | Menú ⋮ → **Añadir a pantalla de inicio** (o **Instalar aplicación**) |
| iPhone / iPad | Safari | **Compartir** → **Añadir a pantalla de inicio** |

Queda el icono de YTAUTO y se abre a pantalla completa, como una app. El ordenador tiene que seguir encendido.

## Sin ordenador
La demostración pública (Netlify o el bot de Telegram) también se instala igual en el móvil, pero solo enseña la
app: no produce vídeos. Ver `instaladores/web/LEEME.md`.
