import type { ProjectSpec } from "./types";

export const YT_MUSIC_PROVIDER = "youtube_audio_library";

export const MUSIC_CHOICES = [
  { id: "auto", label: "Automática (gratuita)" },
  { id: "youtube", label: "Biblioteca de audio de YouTube Studio" },
  { id: "none", label: "Sin música" },
] as const;

/** Campos del proyecto según la música elegida: la de YouTube va como proveedor preferido de la categoría música. */
export function musicSpec(choice: string, style: string): Pick<ProjectSpec, "music" | "preferred_providers"> {
  if (choice === "none") return { music: "none", preferred_providers: {} };
  const music = style.trim() || null;
  if (choice === "youtube") return { music, preferred_providers: { music: YT_MUSIC_PROVIDER } };
  return { music, preferred_providers: {} };
}

export interface MusicWarning { level: "warn" | "info"; text: string; link?: string }

/** Avisos al elegir la música de YouTube: sin pistas importadas, o publicación fuera de YouTube. */
export function musicWarnings(choice: string, usableTracks: number | null, platforms: string[]): MusicWarning[] {
  if (choice !== "youtube") return [];
  const out: MusicWarning[] = [];
  if (usableTracks === 0)
    out.push({ level: "warn", text: "Aún no has importado pistas de la Biblioteca de audio: el vídeo usará la música automática.", link: "#/music" });
  const off = platforms.filter((p) => p !== "youtube_shorts");
  if (off.length)
    out.push({ level: "info", text: "La música de la Biblioteca de audio es segura en YouTube; YouTube no garantiza su uso en TikTok o Instagram. Esos paquetes llevarán un aviso para que revises la licencia de la pista." });
  return out;
}
