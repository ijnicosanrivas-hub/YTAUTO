/** Monitor de tokens: textos y cálculos puros (probados en monitor.test.ts). */
import type { LiveStatus } from "./types";

export const STATUS: Record<LiveStatus, { label: string; icon: string; cls: string }> = {
  ok: { label: "Con margen", icon: "check", cls: "s-ok" },
  aviso: { label: "Cerca del límite", icon: "alert", cls: "s-limited" },
  freno: { label: "Frenada por tu límite", icon: "alert", cls: "s-error" },
  agotada: { label: "Agotada por Claude", icon: "alert", cls: "s-error" },
  inactiva: { label: "Desactivada", icon: "close", cls: "s-disabled" },
};

/** «quedan 12 min», «1 h 05 min», «menos de 1 min». */
export function duration(minutes: number | null | undefined): string {
  if (minutes == null || !Number.isFinite(minutes)) return "—";
  if (minutes < 1) return "menos de 1 min";
  const m = Math.round(minutes);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${String(m % 60).padStart(2, "0")} min`;
}

/** Minutos que faltan hasta `target` (ISO o epoch en segundos), nunca negativos; null si no hay fecha. */
export function minutesUntil(target: string | number | null | undefined, now: number = Date.now()): number | null {
  if (target == null) return null;
  const t = typeof target === "number" ? target * 1000 : Date.parse(target);
  if (Number.isNaN(t)) return null;
  return Math.max(0, (t - now) / 60000);
}

/** Hora local «14:05» de un ISO o epoch (s). */
export function clock(target: string | number | null | undefined): string {
  if (target == null) return "—";
  const d = new Date(typeof target === "number" ? target * 1000 : target);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

/** Color de la barra según el porcentaje usado (los colores de estado van siempre con su texto). */
export function meterTone(pct: number | null | undefined, warn = 80): "ok" | "warn" | "stop" {
  if (pct == null) return "ok";
  if (pct >= 100) return "stop";
  return pct >= warn ? "warn" : "ok";
}

/** «hace 12 s», «hace 3 min», «hace 2 h». */
export function ago(iso: string, now: number = Date.now()): string {
  const s = Math.max(0, (now - Date.parse(iso)) / 1000);
  if (s < 60) return `hace ${Math.round(s)} s`;
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  return `hace ${Math.round(s / 3600)} h`;
}
