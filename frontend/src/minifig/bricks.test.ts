import { describe, expect, it } from "vitest";
import { BRICK_H, PITCH, PLATE_H, ellipseStuds, roundPlateStuds, rnd } from "./bricks";
import { BURST_COUNT, burstPosition, seedFrom } from "./fx";
import { LDU } from "./styleBible";

describe("ladrillos a escala real", () => {
  it("el taco, el ladrillo y la placa guardan las proporciones LEGO", () => {
    expect(PITCH).toBeCloseTo(20 * LDU, 9); // 8 mm
    expect(BRICK_H / PLATE_H).toBeCloseTo(3, 9); // un ladrillo = 3 placas
    expect(BRICK_H / PITCH).toBeCloseTo(1.2, 9); // 9,6 mm de alto por 8 mm de paso
  });

  it("una placa redonda 4×4 tiene 12 tacos (como la pieza real); la 6×6 sigue la misma regla (24)", () => {
    expect(roundPlateStuds(2)).toHaveLength(12);
    expect(roundPlateStuds(3)).toHaveLength(24);
    for (const [x, z] of roundPlateStuds(2)) expect(Math.hypot(x, z)).toBeLessThan(2 * PITCH);
  });

  it("las placas redondas son simétricas", () => {
    for (const r of [2, 3]) {
      const s = roundPlateStuds(r);
      const sx = s.reduce((a, [x]) => a + x, 0), sz = s.reduce((a, [, z]) => a + z, 0);
      expect(Math.abs(sx)).toBeLessThan(1e-9);
      expect(Math.abs(sz)).toBeLessThan(1e-9);
    }
  });

  it("la plataforma elíptica solo lleva tacos dentro de la elipse y es simétrica", () => {
    const a = 8.6, b = 7.6;
    const studs = ellipseStuds(a, b);
    expect(studs.length).toBeGreaterThan(300);
    for (const [x, z] of studs) expect((x / a) ** 2 + (z / b) ** 2).toBeLessThanOrEqual(1);
    expect(Math.abs(studs.reduce((s, [x]) => s + x, 0))).toBeLessThan(1e-6);
    expect(Math.abs(studs.reduce((s, [, z]) => s + z, 0))).toBeLessThan(1e-6);
    for (const [x, z] of studs) {
      expect(Math.abs(Math.abs((x / PITCH) % 1) - 0.5)).toBeLessThan(1e-9); // centrados en cada taco de la rejilla
      expect(Math.abs(Math.abs((z / PITCH) % 1) - 0.5)).toBeLessThan(1e-9);
    }
    expect(new Set(studs.map(([x, z]) => `${x.toFixed(4)}:${z.toFixed(4)}`)).size).toBe(studs.length); // sin tacos repetidos
    expect(ellipseStuds(2, 2).length).toBeLessThan(studs.length);
  });

  it("el pseudoaleatorio es determinista (la sala es idéntica en cada carga)", () => {
    expect(rnd(5)).toBe(rnd(5));
    expect(rnd(5)).not.toBe(rnd(6));
  });
});

describe("efectos de ladrillos", () => {
  it("el confeti parte de la cabeza, sube y cae (balística)", () => {
    const [x0, y0, z0] = burstPosition(3, 0, 0);
    [x0, y0, z0].forEach((n) => expect(n).toBeCloseTo(0, 9));
    const ys = Array.from({ length: 30 }, (_, k) => burstPosition(3, 0, k * 0.1)[1]);
    expect(Math.max(...ys)).toBeGreaterThan(0.2);
    expect(ys[ys.length - 1]).toBeLessThan(Math.max(...ys));
  });
  it("es determinista y cada pieza sigue su propia trayectoria", () => {
    expect(burstPosition(3, 2, 0.5)).toEqual(burstPosition(3, 2, 0.5));
    const ends = new Set(Array.from({ length: BURST_COUNT }, (_, i) => burstPosition(3, i, 0.8).join()));
    expect(ends.size).toBe(BURST_COUNT);
  });
  it("la semilla viene del instante de finalización (mismo confeti en cada fotograma)", () => {
    expect(seedFrom("2026-11-16T10:00:00Z")).toBe(seedFrom("2026-11-16T10:00:00Z"));
    expect(seedFrom("2026-11-16T10:00:00Z")).not.toBe(seedFrom("2026-11-16T10:00:07Z"));
    expect(seedFrom(null)).toBe(7);
  });
});
