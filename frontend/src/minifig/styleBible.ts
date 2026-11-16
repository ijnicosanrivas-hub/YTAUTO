/**
 * STYLE BIBLE — minifigura LEGO Batman (diseño maestro).
 *
 * Es la ÚNICA fuente de proporciones, materiales e iluminación. Los nueve personajes se construyen
 * con la misma plantilla (`Minifig.tsx`) a partir de estas constantes: una variante solo puede cambiar
 * colores, estampados y accesorios, nunca dimensiones.
 * Unidades: 1.0 = ancho aproximado de dos tacos. Altura total de la figura ≈ 1.24.
 */
export const BODY = {
  legs: { w: 0.24, h: 0.3, d: 0.26, x: 0.13 }, // cada pierna; centro en x = ±x
  hips: { w: 0.54, h: 0.12, d: 0.28 },
  torso: { wBottom: 0.54, wTop: 0.46, h: 0.5, d: 0.28 },
  neck: { r: 0.07, h: 0.03 },
  head: { r: 0.2, h: 0.24 }, // cabeza cilíndrica
  headStud: { r: 0.075, h: 0.05 },
  arm: { r: 0.07, len: 0.28, shoulderX: 0.3 }, // brazo recto de una pieza, pivota en el hombro
  hand: { r: 0.065, tube: 0.03, arc: Math.PI * 1.55 }, // pinza en C
} as const;

export const FIGURE_HEIGHT = BODY.legs.h + BODY.hips.h + BODY.torso.h + BODY.neck.h + BODY.head.h; // 1.19 (sin taco)
export const SHOULDER_Y = BODY.legs.h + BODY.hips.h + BODY.torso.h - 0.06;
export const HEAD_Y = BODY.legs.h + BODY.hips.h + BODY.torso.h + BODY.neck.h; // base de la cabeza

/** Paleta de plásticos LEGO (colores sólidos y saturados). */
export const PLASTIC = {
  skin: "#F2CD37",
  black: "#1B1D24",
  darkGrey: "#3A3F4B",
  grey: "#9BA0A6",
  white: "#F4F4F4",
  yellow: "#FFD400",
  green: "#2FBF5B",
  darkGreen: "#157A3A",
  purple: "#7B2FBF",
  darkPurple: "#4A1B7A",
  blue: "#2F6FDB",
  red: "#D6232B",
  orange: "#E8731A",
  tan: "#D7A86E",
  flesh: "#E9B58C",
} as const;

/** Material único de plástico moldeado: mismo brillo, barniz y rugosidad en toda la escena. */
export const MATERIAL = {
  roughness: 0.32,
  metalness: 0,
  clearcoat: 0.7,
  clearcoatRoughness: 0.2,
  envMapIntensity: 0.9,
} as const;

/** Escala con la que se coloca la figura en la sala (idéntica para los nueve; el jefe no se agranda). */
export const FIGURE_SCALE = 1.6;

/** Todos los personajes llevan los mismos estados de animación (compatibles entre sí). */
export const ANIMATION_STATES = ["wait", "move", "work", "interact", "finish", "error"] as const;
export type AnimationState = (typeof ANIMATION_STATES)[number];
