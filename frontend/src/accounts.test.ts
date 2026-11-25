import { describe, expect, it } from "vitest";
import { creditsLeft, fmtCredits, paidAccounts } from "./accounts";
import type { AccountsView } from "./types";

const base = (): AccountsView => ({
  always: [],
  elevenlabs: { linked: true, has_key: true, models: {}, plans: {}, always_authorized: false,
    subscription: { tier: "creator", used: 115000, limit: 121000, remaining: 6000, pct: 95, resets_at_unix: null, commercial_use: true, can_extend: false } },
  higgsfield: {
    cli_path: "/x/hf", status: { installed: true, logged_in: true, credits: 900, message: "" }, video_models: {}, image_models: {},
    plans: { plus: { label: "Plus", credits: 1200, price_eur: 59 } },
    video: { linked: true, role: "primary", model: "kling3_0_turbo", max_per_video: 3 },
    image: { linked: false, role: null, model: null, max_per_video: null },
    price_per_credit_eur: 0.049, reserve_credits: 60, require_balance_check: true,
    always_authorized: { higgsfield_video: false, higgsfield_image: false }, help: { api: "", cli: "" },
  },
});

describe("cuentas conectadas", () => {
  it("formatea créditos y descuenta la reserva", () => {
    expect(fmtCredits(121000)).toMatch(/121.000/);
    expect(fmtCredits(null)).toBe("—");
    expect(creditsLeft(100, 60)).toBe(40);
    expect(creditsLeft(30, 60)).toBe(0);
    expect(creditsLeft(null, 60)).toBeNull();
  });

  it("solo ofrece autorizar las cuentas vinculadas y avisa del saldo bajo", () => {
    const list = paidAccounts(base());
    expect(list.map((a) => a.id)).toEqual(["elevenlabs", "higgsfield_video"]);
    expect(list[0].low).toBe(true); // quedan menos del 10 %
    expect(list[1].low).toBe(false);
  });

  it("no pregunta por las que ya tienen autorización permanente", () => {
    const a = base();
    a.elevenlabs.always_authorized = true;
    a.higgsfield.always_authorized.higgsfield_video = true;
    expect(paidAccounts(a)).toEqual([]);
    expect(paidAccounts(null)).toEqual([]);
  });
});
