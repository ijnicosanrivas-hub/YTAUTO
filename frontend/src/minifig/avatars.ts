/**
 * Personajes 3D de los perfiles GTA VI, YouTube Kids y Deportes (estilo «chibi», no LEGO).
 * Datos puros: el componente `Avatar` los dibuja y los anima con el mismo estado real que las minifiguras.
 * Si el usuario sube la imagen oficial de un personaje, la sala la usa en su lugar.
 */
export type HeadKind = "human" | "dog" | "pig" | "fox" | "shark" | "baby";
export type HairStyle = "short" | "bun" | "long" | "bald" | "curly" | "tuft" | "dreads" | "ponytail" | "slick";
export type TopStyle = "tee" | "shirt" | "suit" | "hoodie" | "dress" | "coat" | "jersey" | "tank" | "overalls";
export type Item = "camera" | "mic" | "clipboard" | "whistle" | "phone" | "briefcase" | "headphones" | "megaphone"
  | "stethoscope" | "book" | "flag" | "trophy" | "binoculars" | "laptop" | "drum" | "balloon" | "bone" | "cards";

export interface AvatarSpec {
  head: HeadKind;
  skin: string;
  hair?: { color: string; style: HairStyle };
  ears?: string; // animales: color de las orejas
  snout?: string; // animales: color del hocico
  top: string;
  topStyle: TopStyle;
  pattern?: { kind: "hawaiian" | "stripes" | "dots"; color: string };
  number?: string; // dorsal de camiseta
  bottom: string;
  shoes: string;
  hat?: { kind: "cap" | "beanie" | "police" | "cowboy" | "crown" | "headband" | "beret"; color: string };
  glasses?: "sun" | "round";
  beard?: string;
  chain?: boolean; // cadena dorada
  item?: Item;
  scale?: number;
}

type Profile = Record<string, AvatarSpec>;

const GTA6: Profile = {
  chief: { head: "human", skin: "#e0b48f", hair: { color: "#3b2a1e", style: "short" }, beard: "#3b2a1e", top: "#5b6b4d", topStyle: "tee", bottom: "#2b3a55", shoes: "#3a2a1c", item: "briefcase" },
  director: { head: "human", skin: "#c98f68", hair: { color: "#1c130f", style: "ponytail" }, top: "#f4f1ea", topStyle: "tank", bottom: "#33476e", shoes: "#f2f2f2", item: "phone", glasses: "sun" },
  scriptwriter: { head: "human", skin: "#efc9a5", hair: { color: "#8a5a2b", style: "curly" }, beard: "#8a5a2b", top: "#2f855a", topStyle: "shirt", pattern: { kind: "hawaiian", color: "#fbd38d" }, bottom: "#7c6a4f", shoes: "#4a3b2a", hat: { kind: "cap", color: "#1a202c" }, glasses: "round", item: "book" },
  resources: { head: "human", skin: "#c48b61", hair: { color: "#9aa0a6", style: "slick" }, top: "#2d3748", topStyle: "suit", bottom: "#1a202c", shoes: "#0d0d0d", item: "briefcase" },
  voice: { head: "human", skin: "#6b4430", hair: { color: "#111", style: "bald" }, top: "#7c3aed", topStyle: "shirt", bottom: "#111827", shoes: "#f8fafc", chain: true, glasses: "sun", item: "mic" },
  editor: { head: "human", skin: "#e8b991", hair: { color: "#2a1d14", style: "short" }, top: "#06b6d4", topStyle: "hoodie", bottom: "#374151", shoes: "#ef4444", hat: { kind: "cap", color: "#f472b6" }, item: "camera" },
  sound: { head: "human", skin: "#5c3a26", hair: { color: "#111", style: "dreads" }, top: "#111827", topStyle: "hoodie", bottom: "#1f2937", shoes: "#f97316", chain: true, item: "headphones" },
  reviewer: { head: "human", skin: "#f1c6a8", hair: { color: "#e5e7eb", style: "short" }, beard: "#e5e7eb", top: "#0ea5e9", topStyle: "shirt", pattern: { kind: "hawaiian", color: "#f97316" }, bottom: "#d6c7a1", shoes: "#6b4f3a", glasses: "sun", hat: { kind: "cowboy", color: "#c2a46b" }, item: "binoculars" },
  publisher: { head: "human", skin: "#7a4a32", hair: { color: "#ff4fa3", style: "long" }, top: "#ef4444", topStyle: "tank", bottom: "#111827", shoes: "#ff4fa3", chain: true, glasses: "sun", item: "phone" },
};

const KIDS: Profile = {
  chief: { head: "dog", skin: "#4f8fe6", ears: "#2b5fae", snout: "#c9dcf7", top: "#4f8fe6", topStyle: "tee", bottom: "#4f8fe6", shoes: "#2b5fae", item: "balloon" },
  director: { head: "human", skin: "#f7d7b5", hat: { kind: "beanie", color: "#2563eb" }, top: "#2563eb", topStyle: "overalls", bottom: "#2563eb", shoes: "#1e3a8a", item: "flag" },
  scriptwriter: { head: "pig", skin: "#f9a8c9", ears: "#f472b6", snout: "#f472b6", top: "#ef4444", topStyle: "dress", bottom: "#f9a8c9", shoes: "#111827", item: "book" },
  resources: { head: "dog", skin: "#a9764b", ears: "#6b4423", snout: "#e7cfb3", top: "#1d4ed8", topStyle: "shirt", bottom: "#1d4ed8", shoes: "#1e293b", hat: { kind: "police", color: "#1d4ed8" }, item: "bone" },
  voice: { head: "shark", skin: "#facc15", snout: "#fff7cc", top: "#facc15", topStyle: "tee", bottom: "#facc15", shoes: "#eab308", item: "mic" },
  editor: { head: "baby", skin: "#f8d9bd", hair: { color: "#c08a52", style: "tuft" }, top: "#22c55e", topStyle: "tee", bottom: "#60a5fa", shoes: "#f8fafc", item: "camera" },
  sound: { head: "fox", skin: "#f472b6", ears: "#db2777", snout: "#fde2ef", top: "#f472b6", topStyle: "tee", bottom: "#f472b6", shoes: "#db2777", item: "drum" },
  reviewer: { head: "human", skin: "#7b4a2e", hair: { color: "#1a1a1a", style: "ponytail" }, top: "#f8fafc", topStyle: "coat", bottom: "#a855f7", shoes: "#a855f7", item: "stethoscope", hat: { kind: "headband", color: "#a855f7" } },
  publisher: { head: "human", skin: "#f3c9a5", hair: { color: "#6b4a2b", style: "short" }, top: "#2563eb", topStyle: "shirt", bottom: "#f97316", shoes: "#f97316", hat: { kind: "beanie", color: "#f97316" }, glasses: "round", item: "phone" },
};

const SPORTS: Profile = {
  chief: { head: "human", skin: "#e8bc96", hair: { color: "#b9bcc2", style: "slick" }, top: "#111827", topStyle: "suit", bottom: "#111827", shoes: "#0b0b0b", item: "trophy" },
  director: { head: "human", skin: "#e0ac85", hair: { color: "#2b2b2b", style: "short" }, beard: "#2b2b2b", top: "#14532d", topStyle: "coat", bottom: "#1f2937", shoes: "#111", item: "clipboard" },
  scriptwriter: { head: "human", skin: "#f0c7a4", hair: { color: "#8b5a2b", style: "long" }, top: "#1d4ed8", topStyle: "suit", bottom: "#1e293b", shoes: "#111", item: "mic" },
  resources: { head: "human", skin: "#c58c62", hair: { color: "#3b2a1e", style: "short" }, top: "#0f766e", topStyle: "coat", bottom: "#374151", shoes: "#111", hat: { kind: "cap", color: "#0f766e" }, item: "binoculars" },
  voice: { head: "human", skin: "#8d5a3b", hair: { color: "#111", style: "bald" }, top: "#f97316", topStyle: "shirt", bottom: "#111827", shoes: "#f8fafc", item: "megaphone" },
  editor: { head: "human", skin: "#f2cda9", hair: { color: "#1f1f1f", style: "bun" }, top: "#7e22ce", topStyle: "hoodie", bottom: "#111827", shoes: "#f8fafc", item: "headphones" },
  sound: { head: "human", skin: "#d6a27a", hair: { color: "#c0262d", style: "curly" }, top: "#dc2626", topStyle: "jersey", number: "12", pattern: { kind: "stripes", color: "#fafafa" }, bottom: "#111827", shoes: "#dc2626", item: "drum" },
  reviewer: { head: "human", skin: "#efc3a0", hair: { color: "#111", style: "bald" }, top: "#111111", topStyle: "jersey", number: "", bottom: "#111111", shoes: "#111", item: "whistle" },
  publisher: { head: "human", skin: "#c9926b", hair: { color: "#2a1a10", style: "ponytail" }, top: "#06b6d4", topStyle: "jersey", number: "10", bottom: "#0f172a", shoes: "#06b6d4", item: "phone" },
};

export const AVATARS: Record<string, Profile> = { gta6: GTA6, kids: KIDS, deportes: SPORTS };

export function avatarFor(profile: string, agent: string): AvatarSpec | undefined {
  return AVATARS[profile]?.[agent];
}

/** Alto aproximado (unidades de escena) de un personaje: sirve para colocar su etiqueta encima. */
export function avatarHeight(spec: AvatarSpec | undefined): number {
  if (!spec) return 2;
  const hat = spec.hat ? 0.22 : 0;
  const animal = spec.head === "dog" || spec.head === "fox" ? 0.2 : spec.head === "shark" ? 0.3 : 0;
  return (2.05 + hat + animal) * (spec.scale ?? 1);
}
