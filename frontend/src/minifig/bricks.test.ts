import { describe, expect, it } from "vitest";
import { BRICK_H, PITCH, PLATE_H, batMosaic, roundPlateStuds, rnd, wallBricks, wallCourses } from "./bricks";
import { BURST_COUNT, burstPosition, seedFrom } from "./fx";
import { LDU, PLASTIC } from "./styleBible";

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

  it("el muro se construye en aparejo a soga con ladrillos 2×4 tangentes", () => {
    const wall = wallBricks(15, -1.6);
    expect(wall.length).toBeGreaterThan(300);
    for (const b of wall) {
      expect(b.len / PITCH).toBeCloseTo(4 * 0.992, 6);
      expect(b.thick / PITCH).toBeCloseTo(2, 9);
      expect(b.y).toBeGreaterThan(-1.6); // nunca por debajo del suelo
      expect(Math.hypot(b.x, b.z)).toBeCloseTo(15, 6); // todos sobre el círculo del muro
    }
    // cada hilera está desplazada media pieza respecto a la anterior: hileras alternas con ángulos distintos
    const row = (c: number) => wall.filter((b) => Math.abs(b.y - (-1.6 + c * BRICK_H + BRICK_H / 2)) < 1e-6).map((b) => Math.atan2(b.z, b.x));
    expect(Math.abs(row(0)[0] - row(1)[0])).toBeGreaterThan(1e-3);
    // los tacos solo están en el ladrillo más alto de cada columna
    const tops = wall.filter((b) => b.top).length;
    expect(tops).toBeGreaterThan(30);
    expect(tops).toBeLessThan(wall.length / 5);
  });

  it("el muro es determinista y de altura irregular dentro de límites", () => {
    expect(wallBricks(15, 0).map((b) => b.color)).toEqual(wallBricks(15, 0).map((b) => b.color));
    const hs = Array.from({ length: 64 }, (_, i) => wallCourses((i / 64) * Math.PI * 2));
    expect(Math.min(...hs)).toBeGreaterThanOrEqual(9);
    expect(Math.max(...hs)).toBeLessThanOrEqual(19);
    expect(new Set(hs).size).toBeGreaterThan(4);
    expect(rnd(5)).toBe(rnd(5));
  });

  it("el mosaico del suelo dibuja el murciélago amarillo sobre un óvalo gris", () => {
    const m = batMosaic();
    const yellow = m.filter((s) => s.color === PLASTIC.yellow).length;
    const grey = m.filter((s) => s.color === PLASTIC.darkGrey).length;
    expect(yellow).toBeGreaterThan(60);
    expect(grey).toBeGreaterThan(yellow); // el fondo ocupa más que el emblema
    expect(m.length).toBeLessThan(40 * 24); // las esquinas del óvalo quedan fuera
    // alineado a la rejilla de tacos
    for (const s of m) expect(Math.abs(((s.x / PITCH + 20) % 1) - 0.5)).toBeLessThan(1e-9);
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
