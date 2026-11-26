import { describe, expect, it } from "vitest";
import { estimateAudioCredits, paidAccounts, videoAudioOptions } from "./accounts";
import type { AccountsView, AudioFeatureView } from "./types";

const f = (id: string, enabled: boolean, extra: Partial<AudioFeatureView> = {}): AudioFeatureView => ({
  id, title: id, question: "", what: "", cost: "", min_tier: "free", in_app: true, per_video: true, default: false, enabled, plan_ok: true, ...extra,
});

const accounts = (features: AudioFeatureView[]): AccountsView => ({
  always: [],
  elevenlabs: { linked: true, has_key: true, models: {}, plans: {}, always_authorized: false, features,
    sfx: { linked: true, max_per_video: 4, always_authorized: false },
    subscription: { tier: "creator", used: 0, limit: 121000, remaining: 121000, pct: 0, resets_at_unix: null, commercial_use: true, can_extend: false } },
  higgsfield: { cli_path: null, status: { installed: false, logged_in: false, credits: null, message: "" }, video_models: {}, image_models: {}, plans: {},
    video: { linked: false, role: null, model: null, max_per_video: null }, image: { linked: false, role: null, model: null, max_per_video: null },
    price_per_credit_eur: null, reserve_credits: null, require_balance_check: true, always_authorized: {}, help: { api: "", cli: "" } },
});

describe("audio por vídeo", () => {
  it("solo ofrece lo activado en el cuestionario y que se decide por vídeo", () => {
    const a = accounts([f("expressive", true), f("sfx", false), f("voice_cast", true, { per_video: false }), f("studio", true, { in_app: false })]);
    expect(videoAudioOptions(a).map((x) => x.id)).toEqual(["expressive"]);
    expect(videoAudioOptions(null)).toEqual([]);
  });
  it("estima créditos de voz y efectos", () => {
    expect(estimateAudioCredits(60, [], null)).toBe(900);
    expect(estimateAudioCredits(60, ["expressive", "sfx"], 4)).toBe(1035 + 800);
  });
  it("los efectos con IA piden su autorización de gasto", () => {
    expect(paidAccounts(accounts([])).map((p) => p.id)).toContain("elevenlabs_sfx");
  });
});
