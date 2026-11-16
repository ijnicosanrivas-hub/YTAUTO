/** Geometría de ladrillos LEGO (funciones puras, sin Three.js): muro de la cueva, mosaico del suelo, placas. */
import { BAT_POLY } from "./ops";
import { BRICK, LDU, PLASTIC, STUD } from "./styleBible";

export const PITCH = STUD.pitch * LDU; // separación entre tacos en la escena (0,44)
export const BRICK_H = BRICK.h * LDU;
export const PLATE_H = BRICK.plate * LDU;

/** Pseudoaleatorio determinista: la sala es idéntica en cada carga. */
export function rnd(i: number): number {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

export interface WallBrick {
  x: number; y: number; z: number;
  rot: number; // giro sobre Y: el ladrillo es tangente al muro
  len: number; thick: number; h: number;
  color: string;
  top: boolean; // último ladrillo de su columna: lleva tacos visibles
}

const WALL_TONES = ["#1d2227", "#272d33", "#33393f", "#171b1f", PLASTIC.darkGrey + "", "#2c3238"];

/** Altura (en hileras) de la pared a un ángulo dado: perfil irregular tipo roca construida con ladrillos. */
export function wallCourses(angle: number, min = 9, max = 19): number {
  const w = 0.5 + 0.28 * Math.sin(angle * 3 + 1) + 0.16 * Math.sin(angle * 7 + 2) + 0.1 * Math.sin(angle * 13);
  return Math.max(min, Math.min(max, Math.round(min + (max - min) * w)));
}

/**
 * Muro circular en aparejo a soga: ladrillos 2×4 tangentes, cada hilera desplazada media pieza.
 * Todas las medidas son múltiplos del taco; `floorY` es la cota del suelo.
 */
export function wallBricks(radius: number, floorY: number, brickStuds = 4, thickStuds = 2): WallBrick[] {
  const len = brickStuds * PITCH;
  const out: WallBrick[] = [];
  const count = Math.floor((2 * Math.PI * radius) / len);
  const step = (Math.PI * 2) / count;
  for (let i = 0; i < count; i++) {
    const rows = wallCourses(i * step);
    for (let c = 0; c < rows; c++) {
      const a = (i + (c % 2 ? 0.5 : 0)) * step;
      const k = i * 31 + c * 7;
      out.push({
        x: Math.cos(a) * radius, z: Math.sin(a) * radius, y: floorY + c * BRICK_H + BRICK_H / 2,
        rot: -a + Math.PI / 2, len: len * 0.992, thick: thickStuds * PITCH, h: BRICK_H * 0.992,
        color: WALL_TONES[Math.floor(rnd(k) * WALL_TONES.length)], top: c === rows - 1,
      });
    }
  }
  return out;
}

function inPoly(x: number, y: number, pts: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export interface MosaicStud { x: number; z: number; color: string }

/** Mosaico de tacos de colores: óvalo gris con el murciélago amarillo (como un mosaico LEGO real). */
export function batMosaic(cols = 40, rows = 24): MosaicStud[] {
  const out: MosaicStud[] = [];
  for (let a = 0; a < cols; a++)
    for (let b = 0; b < rows; b++) {
      const nx = ((a + 0.5) / cols) * 100, ny = ((b + 0.5) / rows) * 100;
      const oval = ((nx - 50) / 49) ** 2 + ((ny - 50) / 49) ** 2 <= 1;
      const bat = inPoly(nx, (ny - 50) * 1.15 + 50, BAT_POLY);
      if (!oval) continue;
      out.push({ x: (a - (cols - 1) / 2) * PITCH, z: (b - (rows - 1) / 2) * PITCH, color: bat ? PLASTIC.yellow : PLASTIC.darkGrey });
    }
  return out;
}

/** Posiciones de tacos de una placa redonda de radio `radiusStuds` (en tacos). Una 4×4 redonda real tiene 12 tacos. */
export function roundPlateStuds(radiusStuds: number): [number, number][] {
  const out: [number, number][] = [];
  const even = Number.isInteger(radiusStuds); // anchura par → los tacos caen en medios enteros
  const lo = even ? -radiusStuds : -Math.floor(radiusStuds);
  const hi = even ? radiusStuds - 1 : Math.floor(radiusStuds);
  for (let a = lo; a <= hi; a++)
    for (let b = lo; b <= hi; b++) {
      const x = a + (even ? 0.5 : 0), z = b + (even ? 0.5 : 0);
      if (Math.hypot(x, z) <= radiusStuds - 0.4) out.push([x * PITCH, z * PITCH]);
    }
  return out;
}
