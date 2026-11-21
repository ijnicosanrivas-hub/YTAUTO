/** Figuras 2D recortadas de un render (funciones puras). Se dibujan como carteles que miran a la cámara. */
import type { AnimationState } from "./styleBible";

export interface FigureMeta { anchor_x: number; w: number; h: number }

/** Altura de referencia (px) que equivale a una figura de ≈2 unidades de escena. */
export const REF_PX = 230;
export const FIGURE_UNITS = 2.0;

/** Tamaño en escena y desplazamiento para que el centro de la base quede en el origen. */
export function spriteSize(m: FigureMeta): { width: number; height: number; offsetX: number } {
  const k = FIGURE_UNITS / REF_PX;
  const width = m.w * k;
  return { width, height: m.h * k, offsetX: (0.5 - m.anchor_x) * width };
}

export interface SpriteMotion { y: number; x: number; rot: number; sx: number; sy: number; glow: number }

/** Movimiento del cartel según el estado real del agente (mismo vocabulario que la figura de ladrillos). */
export function spriteMotion(state: AnimationState, t: number, seed = 0, sinceFinish = 0): SpriteMotion {
  const s = (f: number, ph = 0) => Math.sin(t * f + seed + ph);
  const m: SpriteMotion = { y: 0, x: 0, rot: 0, sx: 1, sy: 1, glow: 0 };
  switch (state) {
    case "wait": // respira
      m.sy = 1 + s(1.6) * 0.012; m.sx = 1 - s(1.6) * 0.006; m.rot = s(0.5) * 0.012;
      break;
    case "move": // marcha en el sitio
      m.y = Math.abs(s(7)) * 0.07; m.rot = s(7) * 0.04; m.x = s(3.5) * 0.04;
      break;
    case "work": // trabaja: cabeceo rápido y pulso de brillo
      m.y = Math.abs(s(9)) * 0.025; m.rot = s(4.5) * 0.02; m.sy = 1 + s(9) * 0.01; m.glow = 0.5 + 0.5 * s(5);
      break;
    case "interact": // espera tu decisión: saluda
      m.rot = s(3.2) * 0.07; m.y = Math.abs(s(3.2)) * 0.05; m.glow = 0.25;
      break;
    case "finish": { // salto de celebración
      const u = Math.min(1, sinceFinish / 3.5);
      m.y = Math.abs(Math.sin(u * Math.PI * 3)) * 0.5 * (1 - u); m.rot = Math.sin(u * Math.PI * 6) * 0.05 * (1 - u); m.glow = 1 - u;
      break;
    }
    case "error": // tiembla
      m.x = s(38) * 0.035; m.rot = s(30) * 0.03; m.glow = 0.6;
      break;
  }
  return m;
}

/** Giro (eje Y) para que el cartel mire a la cámara desde la posición `from`. */
export function billboardYaw(cam: [number, number], from: [number, number]): number {
  return Math.atan2(cam[0] - from[0], cam[1] - from[1]);
}

/** Texto de URL del recorte, con el código de acceso si lo hay. */
export function figureUrl(agent: string, token: string | null): string {
  return `/api/figures/${agent}.png${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}
