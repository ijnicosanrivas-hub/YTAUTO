/** Canales y licencias: funciones puras (probadas en logic.test.ts). */
import type { License } from "./types";

export const CHANNEL_KEY = "ytauto.channel";

export function initialChannel(): string {
  try {
    return localStorage.getItem(CHANNEL_KEY) || "general";
  } catch {
    return "general";
  }
}

/** Añade `channel=` a una ruta de la API respetando los parámetros que ya tenga. */
export function withChannel(path: string, channel: string): string {
  return `${path}${path.includes("?") ? "&" : "?"}channel=${encodeURIComponent(channel)}`;
}

/** URL de la imagen de un personaje del perfil (si existe). */
export function figureImage(theme: string, agent: string, token: string | null): string {
  if (import.meta.env.VITE_DEMO === "1") return `/personajes/${agent}.png`; // versión estática (Netlify)
  return `/api/profiles/${theme}/figures/${agent}.png${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

/** Tokens en formato corto: 950 · 12,4 k · 3,1 M. */
export function tokens(n: number | null | undefined): string {
  const v = n ?? 0;
  if (v < 1000) return String(v);
  if (v < 1_000_000) return `${(v / 1000).toFixed(v < 10_000 ? 1 : 0).replace(".", ",")} k`;
  return `${(v / 1_000_000).toFixed(1).replace(".", ",")} M`;
}

/** Licencias agrupadas por canal (en el orden de los canales) para la pantalla de asignación. */
export function groupByChannel(licenses: License[], order: string[]): [string, License[]][] {
  const by = new Map<string, License[]>(order.map((c) => [c, []]));
  for (const l of licenses) {
    if (!by.has(l.channel_id)) by.set(l.channel_id, []);
    by.get(l.channel_id)!.push(l);
  }
  return [...by.entries()];
}

/** Aviso al elegir una licencia: agotada, desactivada, cerca del límite o de otro canal. */
export function licenseWarning(l: License | undefined, channel: string): string | null {
  if (!l) return null;
  if (!l.enabled) return "Desactivada";
  if (l.limited_now) return "Agotada: no se usará hasta su reinicio";
  if (l.usage_pct != null && l.usage_pct >= 90) return `Al ${Math.round(l.usage_pct)} % de su referencia mensual`;
  if (l.channel_id !== channel) return "Prestada de otro canal";
  return null;
}

/** Duración a partir de la respuesta del director («60 s» → 60). */
export function durationFromAnswer(answer: string | undefined): number | null {
  for (const m of (answer ?? "").matchAll(/(\d{2,3})/g)) {
    const v = Number(m[1]);
    if (v >= 45 && v <= 75) return v;
  }
  return null;
}

/** Nombre corto del proyecto a partir de la idea en bruto. */
export function nameFromIdea(idea: string): string {
  const clean = idea.replace(/\s+/g, " ").trim();
  const first = clean.split(/[.!?\n]/)[0] ?? clean;
  return (first.length > 60 ? `${first.slice(0, 57).trimEnd()}…` : first) || "Nuevo vídeo";
}
