import { describe, expect, it } from "vitest";
import { STATUS, ago, clock, duration, meterTone, minutesUntil } from "./monitor";

describe("monitor de tokens", () => {
  it("cada estado tiene texto e icono, no solo color", () => {
    for (const s of Object.values(STATUS)) expect(s.label.length > 3 && s.icon.length > 2).toBe(true);
    expect(STATUS.freno.label).toMatch(/límite/);
  });
  it("formatea duraciones", () => {
    expect(duration(0.4)).toBe("menos de 1 min");
    expect(duration(12.2)).toBe("12 min");
    expect(duration(65)).toBe("1 h 05 min");
    expect(duration(null)).toBe("—");
  });
  it("cuenta atrás hasta una hora ISO o epoch", () => {
    const now = Date.parse("2026-11-25T12:00:00Z");
    expect(minutesUntil("2026-11-25T12:30:00Z", now)).toBe(30);
    expect(minutesUntil(now / 1000 + 600, now)).toBe(10);
    expect(minutesUntil("2026-11-25T11:00:00Z", now)).toBe(0);
    expect(minutesUntil(null, now)).toBeNull();
  });
  it("tono de la barra según el uso", () => {
    expect(meterTone(50)).toBe("ok");
    expect(meterTone(85)).toBe("warn");
    expect(meterTone(100)).toBe("stop");
    expect(meterTone(null)).toBe("ok");
  });
  it("tiempo transcurrido y hora", () => {
    const now = Date.parse("2026-11-25T12:00:00Z");
    expect(ago("2026-11-25T11:59:48Z", now)).toBe("hace 12 s");
    expect(ago("2026-11-25T11:57:00Z", now)).toBe("hace 3 min");
    expect(clock(null)).toBe("—");
  });
});
