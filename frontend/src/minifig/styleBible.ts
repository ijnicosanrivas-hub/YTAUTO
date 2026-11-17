/**
 * STYLE BIBLE v2 — minifigura LEGO Batman (diseño maestro).
 *
 * Medidas tomadas de las piezas oficiales de la biblioteca LDraw (partes 973 torso, 3626b cabeza,
 * 3815 cadera, 3816/3817 piernas, 3818/3819 brazos, 3820 mano). Unidad: LDU (1 LDU = 0,4 mm;
 * un taco = 20 LDU de separación, 12 LDU de diámetro y 4 de alto; un ladrillo = 24 LDU de alto;
 * una placa = 8). El eje Y apunta hacia arriba y los pies están en y = 0.
 * Las variantes solo pueden cambiar colores, estampados y accesorios: nunca estas dimensiones.
 */
export const LDU = 0.022; // unidades de la escena por LDU (una figura mide ≈ 2 unidades)

export const STUD = { pitch: 20, r: 6, h: 4, hollowR: 4.2 } as const;
export const BRICK = { h: 24, plate: 8 } as const;

export const BODY = {
  legs: { w: 18, h: 28, d: 20, x: 9.2, bevel: 1.6 }, // cada pierna; centro en x = ±x
  hips: { w: 36, h: 6, d: 20, bevel: 1.2 },
  torso: { wBottom: 38, wTop: 28.7, wNeck: 24, h: 32, d: 20, bevel: 1.2 }, // trapecio: más ancho abajo
  head: { r: 12, h: 20, bevel: 1.7 }, // cilindro con bordes redondeados
  headStud: { r: 6, h: 4, hollowR: 4.2 },
  arm: { r: 6.5, above: 6.5, below: 22.4, shoulderX: 15.55, shoulderDrop: 9, tilt: 0.1707 }, // 9,782° hacia fuera
  hand: { r: 4, tube: 2, arc: Math.PI * 1.55, wrist: 3 }, // pinza en C (Ø exterior 12)
} as const;

export const LEG_TOP_Y = BODY.legs.h; // la cadera pivota aquí
export const HIPS_TOP_Y = BODY.legs.h + BODY.hips.h;
export const TORSO_TOP_Y = HIPS_TOP_Y + BODY.torso.h;
export const HEAD_BASE_Y = TORSO_TOP_Y;
export const HEAD_TOP_Y = HEAD_BASE_Y + BODY.head.h;
export const SHOULDER_Y = TORSO_TOP_Y - BODY.arm.shoulderDrop;
export const FIGURE_HEIGHT = HEAD_TOP_Y + BODY.headStud.h; // 90 LDU = 36 mm con taco

/** Paleta oficial de colores LEGO (valores de la tabla de Rebrickable/BrickLink). */
export const PLASTIC = {
  skin: "#F2CD37", // Bright Yellow
  black: "#05131D",
  white: "#F2F3F2",
  grey: "#A0A5A9", // Light Bluish Gray
  darkGrey: "#6C6E68", // Dark Bluish Gray
  yellow: "#F2CD37",
  green: "#4B9F4A", // Bright Green
  darkGreen: "#237841",
  lime: "#BBE90B",
  purple: "#81007B",
  darkPurple: "#3F3691",
  blue: "#0055BF",
  red: "#C91A09",
  darkRed: "#720E0F",
  orange: "#FE8A18",
  tan: "#E4CD9E",
  nougat: "#D09168", // piel oscura
  lightNougat: "#F6D7B3",
  blond: "#E4CD9E",
  reddishBrown: "#582A12",
  darkBrown: "#352100",
  lavender: "#A06EB9",
  darkOrange: "#A95500",
  pink: "#DC8FA5",
} as const;

/** Plástico ABS moldeado: brillante pero no espejo (el mismo material para figuras y ladrillos). */
export const MATERIAL = {
  roughness: 0.3,
  metalness: 0,
  clearcoat: 0.45,
  clearcoatRoughness: 0.28,
  envMapIntensity: 0.85,
} as const;

/** Todos los personajes llevan los mismos estados de animación (compatibles entre sí). */
export const ANIMATION_STATES = ["wait", "move", "work", "interact", "finish", "error"] as const;
export type AnimationState = (typeof ANIMATION_STATES)[number];
