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

## Los nueve (diseños oficiales más populares, ver `docs/lego_research.md`)
| Agente | Personaje | Diseño y rasgos |
|---|---|---|
| Jefe | Batman | Traje **gris azulado claro**, capucha negra con orejas, capa, cinturón y emblema amarillos |
| Director | El Acertijo | Torso verde con «?» negro grande, cinturón morado, bombín verde, antifaz morado |
| Guionista | El Joker | Traje morado, pajarita verde, flor en la solapa, pelo verde, cara blanca, sonrisa roja |
| Recursos | Catwoman | Traje negro con líneas moradas, cremallera gris, cinturón dorado, capucha con orejas de gata |
| Voz | Bane | Máscara de luchador con ojos rojos y mangueras verdes, torso desnudo con arneses |
| Editor | Nightwing | Torso negro con V azul, brazos azules, antifaz, pelo negro de pinchos |
| Sonido | El Pingüino | Chistera, monóculo, chaqué con chaleco naranja y pajarita morada, paraguas |
| Revisor | Dos Caras | Cara con mitad quemada, pelo partido, traje partido naranja y morado |
| Publicador | Harley Quinn | Bicolor rojo y negro, antifaz arlequín, coletas alternas, torso y piernas estampados |

Cada figura lleva estampado en **cara** (cejas, pupilas con brillo, sombras), **torso**, **espalda** y **piernas**.

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

## Batcueva (`Batcave.tsx`, `bricks.ts`)
Construida a la **misma escala** que las figuras (el taco de la placa base mide lo que el de su pie):
- Placa base de 64×64 tacos con un **mosaico** del murciélago (tacos amarillos sobre óvalo gris).
- Muro circular de **ladrillos 2×4 en aparejo a soga**, de altura irregular, con tacos en la última hilera.
- Ordenadores y pantalla de mando de ladrillos, Batmóvil, montones de piezas, moneda gigante y el proyector de la señal.
- Cada agente sobre una placa redonda 4×4 de su color (la del jefe, 6×6) y con su propio **atril de trabajo**, cuya
  pantalla solo se enciende mientras el agente está en ejecución.
- Los paquetes de datos entre agentes viajan como **ladrillos amarillos** que giran; al terminar sale confeti de
  ladrillos; al fallar, chispas; al pedir tu decisión, un «!» de ladrillos flota sobre la cabeza.
El anillo de la placa mantiene el color del **estado** real (en espera / ejecución / esperando / error).

## Interfaz LEGO (solo en la sala)
En la **sala 3D** (el resto de pantallas conserva el diseño oscuro anterior) se usa el tema: placa base de tacos como fondo, paneles y botones **como ladrillos** (relieve, fila de
tacos, se hunden al pulsar), barras de progreso de ladrillos con tacos, tipografía redondeada **Lilita One + Nunito**
(libres, SIL OFL, empaquetadas) y la paleta oficial de LEGO. Con `YTAUTO_THEME=classic` vuelve el diseño anterior.

## Calidad gráfica
Botón «Calidad» en la sala: *alta* (brillo, antialiasing, sombras) o *baja* (equipos modestos). Se pasa sola a baja si
los fotogramas caen; se puede forzar con `#/room?calidad=alta|baja`.

## Límites
- Los modelos son **procedurales** (geometría generada en código con Three.js), no mallas importadas de un
  editor 3D: sin ficheros que descargar y siempre idénticos. Son una interpretación fiel de las medidas reales, no
  réplicas oficiales; faltan detalles de molde como los huecos internos de las piernas o las inscripciones de los tacos.
- La tipografía real de LEGO es propietaria: se usan equivalentes libres.
- Verificado con capturas en Chromium con renderizado por software (sin GPU). No se midió el rendimiento en GPU reales.
- Estampados de cara y torso con formas simples; no hay textura de detalle fino.

Uso personal, no distribuible. No se incluyen logotipos ni activos de terceros.
