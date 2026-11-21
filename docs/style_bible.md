# Style Bible — minifiguras LEGO Batman

Guía visual común de los nueve agentes, de la Batcueva y de toda la interfaz (tema `gotham`, estilo LEGO). Es **obligatoria**: la fuente única
está en `frontend/src/minifig/styleBible.ts`; los nueve personajes salen de **una sola plantilla**
(`Minifig.tsx`). Solo cambia la presentación: la funcionalidad del sistema no se toca.

## Diseño maestro v2 (medidas reales, ver `docs/lego_research.md`)
Unidad **LDU** (1 LDU = 0,4 mm; taco = 20 LDU de paso). Las medidas salen de las piezas oficiales de LDraw.
| Pieza | Regla |
|---|---|
| Cabeza | Cilindro torneado de bordes redondeados (radio 12, alto 20) con taco hueco; cara estampada |
| Torso | **Trapecio** biselado de 38 LDU abajo, ≈ 29 arriba, 32 de alto y 20 de fondo, con el estampado ajustado al contorno |
| Brazos | Cilindro recto con hombro redondo, **inclinado 9,782°** hacia fuera como la pieza real |
| Manos | Pinza en C con muñeca, abierta hacia delante |
| Cadera y piernas | Bloques biselados: cadera 36 de ancho, piernas de 18 × 28 que pivotan en la cadera |
| Proporciones | **Idénticas** (`BODY`): ninguna variante puede cambiar una dimensión |
| Material | Un único plástico ABS (`MATERIAL`) con barniz suave; paleta oficial de colores LEGO |
| Iluminación | Un único equipo de luces: ambiente, hemisférica, direccional con sombras, luces de estudio para reflejos y brillo (bloom) |
| Animación | Mismo esqueleto y mismos seis estados para todos; capa de tela que ondea |

La **robustez de Bane** y el resto de rasgos se expresan con estampado y accesorios, **no** con proporciones distintas.

## Qué puede variar una variante (`variants.ts`)
Solo **colores**, **estampados** (datos de dibujo sobre un lienzo 100×100) y **accesorios** (orejas, capa, pelo,
sombrero, paraguas, monóculo, máscara de Bane, flor). Una prueba comprueba que no hay ninguna otra clave.

## Los nueve (versión del último videojuego LEGO Batman, según la imagen de referencia)
| Agente | Personaje | Diseño y objeto en la mano |
|---|---|---|
| Jefe | Batman | Traje gris con óvalo amarillo, capucha negra con orejas, capa larga; **batarang** |
| Director | El Acertijo | Traje verde con «?», corbata morada, antifaz y bombín; **bastón dorado en forma de «?»** |
| Guionista | El Joker | Traje morado, chaleco naranja, pajarita verde, flor, pelo verde; **dentadura de cuerda** |
| Recursos | Catwoman | Capucha con orejas y gafas grandes, líneas moradas, cinturón morado; **látigo** |
| Voz | Bane | **Figura grande** (×1,32): máscara con ojos rojos, **mangueras verdes que suben sobre la cabeza**, arneses |
| Editor | Nightwing | Traje negro y azul, guantes azules, antifaz y pelo de pinchos; **dos bastones de escrima** |
| Sonido | El Pingüino | Chistera, monóculo, **collar de piel**, chaleco gris; **paraguas** |
| Revisor | Dos Caras | Traje blanco a un lado y negro al otro, cara con mitad quemada; **moneda** |
| Publicador | Harley Quinn | **Capucha de bufón** roja y negra con cuernos y bolas, golilla blanca; **gran mazo** |

Todas comparten plantilla, proporciones, material y animaciones; solo Bane tiene un factor de tamaño. Cada figura lleva
estampado en cara, torso, espalda y piernas. Los objetos son geometría procedural (mazo, bastón, látigo, moneda,
dentadura, batarang, escrima, paraguas) y se mueven con la mano del personaje.

## Animaciones (`pose.ts`, iguales para los nueve)
El estado sale **solo** del estado real del agente; no hay movimiento inventado.

| Estado | Cuándo | Gesto |
|---|---|---|
| Espera | Sin actividad | Respira, mira alrededor |
| Movimiento | Recibe una entrega real de otro agente | Marcha en el sitio |
| Trabajo | Agente en ejecución | Teclea ante su consola, cabeza gacha |
| Interacción | Espera tu decisión | Levanta el brazo y te llama |
| Finalización | Acaba de terminar (3,5 s) | Salto de victoria que se apaga |
| Error | Falló | Cabizbajo y temblando |

## Batcueva: el hub de la fábrica (`Hub.tsx`, `hub.ts`, `Batcave.tsx`)
Inspirado en el hub del videojuego (Batcomputer, mesa de trabajo, bóveda de trajes, tablero de desafíos, zona de
entrenamiento, tienda Bat-Mite y garaje de Batmóviles): **cada agente trabaja en su propia instalación y todos reportan a Batman**.
| Agente | Instalación | Qué se anima con su estado real |
|---|---|---|
| Batman | Batcomputer (centro de mando) | El holograma del murciélago y los anillos giran más rápido al trabajar; se gira hacia la pantalla |
| El Acertijo | Tablero de desafíos | Las casillas «?» brillan con pulso |
| El Joker | Muro de casos (hilo rojo) | Los hilos se iluminan |
| Harley Quinn | Garaje del Batmóvil | La plataforma gira más rápido y se encienden los faros |
| Bane | Zona de entrenamiento | El saco se balancea con fuerza |
| Catwoman | Bóveda de trajes | Las vitrinas giran y brillan |
| El Pingüino | Tienda Bat-Mite | El ecualizador y los altavoces bailan |
| Nightwing | Mesa de trabajo | El brazo robótico trabaja y saltan chispas |
| Dos Caras | Mesa de pruebas | El escáner barre y la moneda gira |
En reposo cada personaje **mira a Batman**; al trabajar **se gira hacia su instalación**. Ambiente: cueva de roca con estalactitas,
túneles con arcos de acero, pantalla gigante del murciélago, murciélagos que vuelan, luces propias de cada instalación.

### Clic en un agente
Al pulsar un personaje la **cámara vuela hasta él** (plano sobre el hombro) y se abre su **expediente**: estado real, instalación,
tarea y fase actual con barra de progreso y tiempo, estadísticas (ejecuciones, errores, llamadas a Claude, última duración), fases
que gestiona y **últimas acciones** (eventos reales). `Esc`, el fondo, ✕ o «Vista general» devuelven la cámara. También se puede
abrir directamente con `#/room?agente=editor`.

## Interfaz LEGO (solo en la sala)
En la **sala 3D** (el resto de pantallas conserva el diseño oscuro anterior) se usa el tema: placa base de tacos como fondo, paneles y botones **como ladrillos** (relieve, fila de
tacos, se hunden al pulsar), barras de progreso de ladrillos con tacos, tipografía redondeada **Lilita One + Nunito**
(libres, SIL OFL, empaquetadas) y la paleta oficial de LEGO. Con `YTAUTO_THEME=classic` vuelve el diseño anterior.

## Calidad gráfica
Botón «Calidad» en la sala: *alta* (brillo, antialiasing, sombras) o *baja* (equipos modestos). Se pasa sola a baja si
los fotogramas caen; se puede forzar con `#/room?calidad=alta|baja`.

## Límites
- **No son los modelos oficiales del videojuego.** Los modelos 3D de LEGO Batman: Legacy of the Dark Knight son activos propietarios
  que no están disponibles aquí: las figuras, las instalaciones y la Batcueva son una **recreación propia** procedural, hecha a partir de las
  descripciones públicas del juego y de la imagen de referencia proporcionada.
- Los modelos son **procedurales** (geometría generada en código con Three.js), no mallas importadas de un
  editor 3D: sin ficheros que descargar y siempre idénticos. Son una interpretación fiel de las medidas reales, no
  réplicas oficiales; faltan detalles de molde como los huecos internos de las piernas o las inscripciones de los tacos.
- La tipografía real de LEGO es propietaria: se usan equivalentes libres.
- Verificado con capturas en Chromium con renderizado por software (sin GPU). No se midió el rendimiento en GPU reales.
- Estampados de cara y torso con formas simples; no hay textura de detalle fino.

Uso personal, no distribuible. No se incluyen logotipos ni activos de terceros.

## Figuras desde un render propio (opcional)
Si existe `assets/personajes/` (PNG con transparencia + `meta.json`), la sala dibuja esos recortes como carteles que miran a la cámara
(`SpriteFigure`, animados con el estado real del agente: respiran, marchan, trabajan con brillo, saludan, saltan al terminar, tiemblan en error).
Si no existen, se usan las figuras de ladrillos. Se generan con `scripts/extraer_figuras.py render.jpg --modelo isnet-general-use.onnx`.
`assets/personajes/` se versiona a petición del usuario (recortes de su propio render; ojo si el repositorio es público). Limitación: son imágenes 2D de ≈200 px de alto,
no modelos 3D; vistos de cerca se ven suaves y siempre muestran la cara frontal del render.
