/** Estampados de las figuras como datos (no código): cada variante declara sus operaciones de dibujo. */
export type Op =
  | { k: "rect"; x: number; y: number; w: number; h: number; c: string }
  | { k: "circle"; x: number; y: number; r: number; c: string }
  | { k: "poly"; pts: [number, number][]; c: string }
  | { k: "line"; x1: number; y1: number; x2: number; y2: number; c: string; w?: number }
  | { k: "text"; x: number; y: number; s: string; c: string; size: number };

/** Silueta del murciélago en el lienzo 100×100 (torso de Batman, mosaico del suelo y proyector). */
export const BAT_POLY: [number, number][] = [[18, 42], [34, 36], [42, 30], [46, 35], [50, 27], [54, 35], [58, 30], [66, 36], [82, 42], [72, 54], [64, 47], [56, 58], [50, 53], [44, 58], [36, 47], [28, 54]];

/** Lienzo lógico 100×100 (el origen es la esquina superior izquierda). */
export const CANVAS = 100;

export type Ctx = Pick<CanvasRenderingContext2D,
  "fillRect" | "beginPath" | "arc" | "fill" | "moveTo" | "lineTo" | "closePath" | "stroke" | "fillText"> &
  { fillStyle: unknown; strokeStyle: unknown; lineWidth: number; font: string; textAlign: unknown; textBaseline: unknown; lineCap: unknown };

export function drawOps(ctx: Ctx, ops: Op[], size: number): void {
  const u = size / CANVAS;
  for (const op of ops) {
    ctx.fillStyle = op.c;
    ctx.strokeStyle = op.c;
    switch (op.k) {
      case "rect":
        ctx.fillRect(op.x * u, op.y * u, op.w * u, op.h * u);
        break;
      case "circle":
        ctx.beginPath();
        ctx.arc(op.x * u, op.y * u, op.r * u, 0, Math.PI * 2);
        ctx.fill();
        break;
      case "poly":
        ctx.beginPath();
        op.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x * u, y * u) : ctx.moveTo(x * u, y * u)));
        ctx.closePath();
        ctx.fill();
        break;
      case "line":
        ctx.lineWidth = (op.w ?? 2) * u;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(op.x1 * u, op.y1 * u);
        ctx.lineTo(op.x2 * u, op.y2 * u);
        ctx.stroke();
        break;
      case "text":
        ctx.font = `bold ${op.size * u}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(op.s, op.x * u, op.y * u);
        break;
    }
  }
}
