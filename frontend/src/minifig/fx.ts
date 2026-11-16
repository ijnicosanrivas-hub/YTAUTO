/** Efectos de ladrillos (funciones puras): confeti de ladrillos al terminar y chispas al fallar. */
import { PLASTIC as P } from "./styleBible";
import { rnd } from "./bricks";

export const BURST_COUNT = 14;
export const CONFETTI_COLORS = [P.red, P.yellow, P.blue, P.green, P.orange, P.white];
export const SPARK_COLORS = [P.red, P.orange, P.darkRed];

/** Posición (unidades de la escena, relativa a la cabeza) de la pieza i, t segundos tras el disparo. Balística simple. */
export function burstPosition(seed: number, i: number, t: number, up = 2.6, g = 4.2): [number, number, number] {
  const a = rnd(seed * 17 + i * 3) * Math.PI * 2;
  const sp = 0.5 + rnd(seed * 29 + i * 5) * 1.1;
  const vy = up * (0.55 + rnd(seed * 41 + i * 7) * 0.7);
  return [Math.cos(a) * sp * t, vy * t - 0.5 * g * t * t, Math.sin(a) * sp * t];
}

/** Semilla estable a partir del instante en que terminó (el mismo confeti en cada fotograma). */
export function seedFrom(text: string | null): number {
  let h = 7;
  for (const ch of text ?? "") h = (h * 31 + ch.charCodeAt(0)) % 9973;
  return h;
}
