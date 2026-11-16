# Style Bible — minifiguras LEGO Batman

Guía visual común de los nueve agentes y de la Batcueva (tema `gotham`). Es **obligatoria**: la fuente única
está en `frontend/src/minifig/styleBible.ts`; los nueve personajes salen de **una sola plantilla**
(`Minifig.tsx`). Solo cambia la presentación: la funcionalidad del sistema no se toca.

## Diseño maestro (se define una vez, los nueve lo heredan)
| Pieza | Regla |
|---|---|
| Cabeza | Cilindro con taco superior; cara estampada (ojos, boca, rasgos) |
| Torso | Caja ahusada de juguete con el estampado del traje al frente |
| Brazos | Cilindro recto de una pieza, pivotan en el hombro |
| Manos | Pinza en C (toro abierto), sin dedos |
| Cadera y piernas | Cadera ancha + dos bloques rectos que pivotan en la cadera |
| Altura y proporciones | **Idénticas** (`BODY`): ninguna variante puede cambiar una dimensión |
| Material | Un único plástico moldeado (`MATERIAL`): barniz, rugosidad y reflejos iguales |
| Iluminación | Un único equipo de luces para toda la sala (ambiente, hemisférica, direccional con sombras, luces de estudio para los reflejos) |
| Animación | Mismo esqueleto y mismos seis estados para todos |

La **robustez de Bane** y el resto de rasgos se expresan con estampado y accesorios (arneses, máscara), **no** con
proporciones distintas: así los nueve parecen fabricados para el mismo videojuego.

## Qué puede variar una variante (`variants.ts`)
Solo **colores**, **estampados** (datos de dibujo sobre un lienzo 100×100) y **accesorios** (orejas, capa, pelo,
sombrero, paraguas, monóculo, máscara de Bane, flor). Una prueba comprueba que no hay ninguna otra clave.

## Los nueve (identidades fijadas, sin cambios)
| Agente | Personaje | Rasgos conservados |
|---|---|---|
| Jefe | Batman | Traje negro, capucha con orejas, capa, emblema del murciélago, cinturón amarillo |
| Director | El Acertijo | Verde y morado, sombrero bombín, antifaz, signos «?» |
| Guionista | El Joker | Pelo verde, traje morado, chaleco verde, cara blanca, sonrisa roja, flor |
| Recursos | Catwoman | Traje y capucha negros con orejas de gata, ojos verdes, cinturón dorado |
| Voz | Bane | Complexión marcada (estampado), arneses, máscara respiratoria con tubos |
| Editor | Nightwing | Traje oscuro con detalles azules (brazos, «ala» del pecho), antifaz, pelo negro |
| Sonido | El Pingüino | Frac con pajarita, chistera, monóculo, paraguas |
| Revisor | Dos Caras | Cara, traje, brazos y piernas divididos en dos mitades |
| Publicador | Harley Quinn | Rojo y negro, coletas bicolor, rombos, antifaz |

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

## Batcueva (`Batcave.tsx`)
Placa base con tacos, columnas de roca hechas de ladrillos oscuros, ordenadores con pantallas, un Batmóvil de
ladrillos, montones de piezas y el proyector de la señal del murciélago. Cada agente se sitúa sobre una placa
redonda con su color. El **anillo** de la placa mantiene el color del **estado** real (en espera / ejecución /
esperando / error).

## Límites
- Los modelos son **procedurales** (geometría generada en código con Three.js), no mallas importadas de un
  editor 3D: sin ficheros de modelos que descargar y siempre idénticos. Son una interpretación fiel del estilo, no
  réplicas oficiales.
- Verificado con capturas en Chromium (renderizado por software). No se midió el rendimiento en GPU reales; con
  equipos muy modestos baja la resolución o usa `YTAUTO_THEME=classic`.
- Los estampados se dibujan con operaciones simples (cara y torso); no hay textura de detalle fino.

Uso personal, no distribuible. No se incluyen logotipos ni activos de terceros.
