/** Geometría de ladrillos LEGO (funciones puras, sin Three.js): placas redondas y elípticas con sus tacos. */
import { BRICK, LDU, STUD } from "./styleBible";

export const PITCH = STUD.pitch * LDU; // separación entre tacos en la escena (0,44)
export const BRICK_H = BRICK.h * LDU;
export const PLATE_H = BRICK.plate * LDU;

/** Pseudoaleatorio determinista: la sala es idéntica en cada carga. */
export function rnd(i: number): number {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
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


/** Tacos de una placa elíptica (plataforma de exposición): los que caben en la elipse de semiejes a×b (en unidades de la escena). */
export function ellipseStuds(a: number, b: number): [number, number][] {
  const out: [number, number][] = [];
  const nx = Math.floor(a / PITCH), nz = Math.floor(b / PITCH);
  for (let i = -nx; i < nx; i++)
    for (let j = -nz; j < nz; j++) {
      const x = (i + 0.5) * PITCH, z = (j + 0.5) * PITCH;
      if ((x / (a - PITCH * 0.45)) ** 2 + (z / (b - PITCH * 0.45)) ** 2 <= 1) out.push([x, z]);
    }
  return out;
}
