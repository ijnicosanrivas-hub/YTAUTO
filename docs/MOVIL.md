# Usar YTAUTO desde el iPhone

**Cómo funciona:** el programa corre en tu **PC con Windows** (es quien produce los vídeos) y el iPhone lo maneja
desde el navegador **Safari**, por tu Wi-Fi de casa. El iPhone no instala nada. **El PC debe estar encendido** y el
programa abierto mientras lo usas.

## Una sola vez
1. Instala YTAUTO en el PC siguiendo `docs/WINDOWS.md` (si aún no lo hiciste).
2. Conecta el **iPhone al mismo Wi-Fi** que el PC (no la red de invitados).

## Cada vez que quieras usarlo desde el iPhone
1. En el PC, haz doble clic en **`INICIAR_WINDOWS_MOVIL.bat`** (en lugar de `INICIAR_WINDOWS.bat`).
2. La primera vez, Windows pregunta por el **Firewall**: pulsa **«Permitir acceso»** (marca *Redes privadas*).
3. En la ventana negra aparece algo así:
   ```
   ACCESO DESDE EL IPHONE (mismo Wi-Fi que este PC): abre en Safari uno de estos enlaces:
     http://192.168.1.34:8000/?token=Xk3...
   ```
4. **Lleva ese enlace al iPhone.** Escribirlo a mano es incómodo; lo más fácil:
   - Copia el enlace de la ventana negra (clic derecho sobre el texto seleccionado) y **envíatelo a ti mismo** por
     WhatsApp, correo o iMessage; ábrelo en el iPhone y pulsa el enlace.
   - También queda guardado en el archivo `data\acceso_movil.txt` del programa.
5. Safari abre YTAUTO. La primera vez guarda tu código de acceso: **no hay que volver a escribirlo**
   (si algún día lo pide, escríbelo en el recuadro «Código de acceso»; es la parte que va después de `token=`).

> Truco: en Safari pulsa **Compartir → «Añadir a pantalla de inicio»** y tendrás un icono como una app.

## Qué esperar en el iPhone
- Todo lo importante funciona: crear vídeos, aprobar el guion, ver el vídeo, descargar los MP4 y los textos.
- La **sala 3D** es pesada para un teléfono: se pone sola en *calidad baja*; si va lenta, usa Dashboard y Proyectos.
- Los vídeos se producen en el PC (4–8 min cada uno); puedes cerrar Safari y volver más tarde.

## Si no carga
| Qué ves | Qué hacer |
|---|---|
| Safari no conecta | Comprueba que el iPhone y el PC están en el **mismo Wi-Fi** (no «invitados», no datos móviles) |
| Sigue sin conectar | En el PC, cierra la ventana negra y ábrela otra vez; acepta el Firewall. Si ya lo rechazaste: *Configuración de Windows → Firewall → Permitir una aplicación* y marca Python en redes privadas |
| La dirección no sirve | Los PC cambian de dirección al reiniciar el router: cierra y abre el `.bat` y usa el enlace nuevo |
| Pide «Código de acceso» | Escribe lo que va tras `token=` en el enlace (o abre el enlace completo otra vez) |
| Un VPN activo en el PC | Desactívalo mientras lo usas desde el móvil |

## Seguridad (léelo)
- Es una conexión **HTTP sin cifrar dentro de tu casa**. Úsalo solo en tu **Wi-Fi doméstico**, **nunca en Wi-Fi públicos**.
- Quien tenga el enlace (con el código) y esté en tu red puede manejar el programa: no lo compartas. El código se guarda en
  `data\lan_token.txt` (fuera de git); bórralo para generar uno nuevo.
- **Nada se publica ni se gasta sin tu autorización**, también desde el móvil.
- `INICIAR_WINDOWS.bat` (el normal) **no** abre el programa a la red: solo el PC.

## Fuera de casa
No funciona con este método (el PC está en tu red local). Existen servicios de «red privada» gratuitos (por ejemplo
Tailscale) que lo permitirían, pero **no están probados** con este programa y no se recomiendan sin conocerlos.

## En macOS / Linux
`python -m ytauto.api.server --lan` hace lo mismo (muestra los enlaces con el código).

## Qué está comprobado
Probado en Linux: el servidor en modo móvil exige el código (rechaza sin él y con uno incorrecto), la interfaz lo
adopta del enlace y lo pide si falta, y la pantalla se ve bien en un iPhone **emulado** (Chromium). **No** se ha probado en
un iPhone real ni con el Firewall de un Windows real.
