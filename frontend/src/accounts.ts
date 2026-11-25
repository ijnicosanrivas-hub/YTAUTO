import type { AccountsView } from "./types";

/** 121000 → «121.000»; null → «—». */
export function fmtCredits(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("es-ES");
}

/** Créditos realmente utilizables (lo que queda menos la reserva intocable). */
export function creditsLeft(credits: number | null | undefined, reserve: number | null | undefined): number | null {
  if (credits == null) return null;
  return Math.max(0, credits - (reserve ?? 0));
}

export interface PaidAccount { id: string; label: string; detail: string; low: boolean }

/** Cuentas de pago vinculadas que un vídeo nuevo puede autorizar (puerta `spend:<id>`). */
export function paidAccounts(a: AccountsView | null): PaidAccount[] {
  if (!a) return [];
  const out: PaidAccount[] = [];
  const e = a.elevenlabs;
  if (e.linked && e.has_key && !e.always_authorized) {
    const s = e.subscription;
    out.push({ id: "elevenlabs", label: "Voz ElevenLabs", detail: s ? `${fmtCredits(s.remaining)} créditos libres` : "saldo sin leer",
      low: !!s && s.limit > 0 && s.remaining / s.limit < 0.1 });
  }
  const h = a.higgsfield;
  const left = h.status.credits;
  const total = h.plans.plus?.credits ?? null;
  const low = left != null && total != null && left / total < 0.1;
  if (h.video.linked && !h.always_authorized.higgsfield_video)
    out.push({ id: "higgsfield_video", label: "Clips de vídeo Higgsfield", detail: `hasta ${h.video.max_per_video ?? "∞"} clips · ${fmtCredits(left)} créditos`, low });
  if (h.image.linked && !h.always_authorized.higgsfield_image)
    out.push({ id: "higgsfield_image", label: "Imágenes Higgsfield", detail: `hasta ${h.image.max_per_video ?? "∞"} imágenes · ${fmtCredits(left)} créditos`, low });
  return out;
}
