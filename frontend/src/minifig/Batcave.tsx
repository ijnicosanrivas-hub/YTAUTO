/**
 * Batcueva v2, construida con ladrillos a escala real respecto a las figuras: tacos de 6 LDU de radio,
 * ladrillos de 24 LDU de alto, muro en aparejo a soga, mosaico de tacos, placa base de 64×64 tacos.
 */
import { Lightformer, Sparkles } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { BRICK_H, batMosaic, PITCH, PLATE_H, rnd, roundPlateStuds, wallBricks } from "./bricks";
import { plastic } from "./Minifig";
import { BAT_POLY, drawOps, type Op } from "./ops";
import { LDU, PLASTIC as P, STUD } from "./styleBible";

export const FLOOR_Y = -1.6;
export { PLATE_H };
/** Radio (en unidades de la escena) de la placa redonda de cada personaje: 4×4 tacos; la del jefe, 6×6. */
export const plateRadius = (big: boolean) => (big ? 3 : 2) * PITCH;

// --- taco compartido -------------------------------------------------------------------------
let studGeo: THREE.LatheGeometry | null = null;
function stud(): THREE.LatheGeometry {
  if (!studGeo) {
    const r = STUD.r * LDU, h = STUD.h * LDU, b = 0.5 * LDU;
    studGeo = new THREE.LatheGeometry([[0, 0], [r, 0], [r, h - b], [r - b, h], [0, h]].map(([x, y]) => new THREE.Vector2(x, y)), 18);
  }
  return studGeo;
}

interface StudItem { x: number; y: number; z: number; color: string }

/** Tacos instanciados (una sola llamada de dibujo) con color por taco. */
function StudInstances({ items }: { items: StudItem[] }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const d = new THREE.Object3D();
    const c = new THREE.Color();
    items.forEach((it, i) => {
      d.position.set(it.x, it.y, it.z);
      d.updateMatrix();
      m.setMatrixAt(i, d.matrix);
      m.setColorAt(i, c.set(it.color));
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [items]);
  return <instancedMesh ref={ref} args={[stud(), undefined, items.length]} castShadow receiveShadow material={plastic("#ffffff")} />;
}

function TopStuds({ w, d, y, color }: { w: number; d: number; y: number; color: string }) {
  const items = useMemo(() => {
    const out: StudItem[] = [];
    const cols = Math.max(1, Math.round(w / PITCH)), rows = Math.max(1, Math.round(d / PITCH));
    for (let a = 0; a < cols; a++) for (let b = 0; b < rows; b++) out.push({ x: (a - (cols - 1) / 2) * PITCH, y, z: (b - (rows - 1) / 2) * PITCH, color });
    return out;
  }, [w, d, y, color]);
  return <StudInstances items={items} />;
}

/** Ladrillo suelto: cuerpo biselado + tacos. Dimensiones en tacos (ancho, fondo) y alturas de ladrillo. */
export function Brick({ w, d, h = 1, color, pos, rot = 0 }: { w: number; d: number; h?: number; color: string; pos: [number, number, number]; rot?: number }) {
  const H = h * BRICK_H;
  const geo = useMemo(() => new RoundedBoxGeometry(w * PITCH * 0.995, H * 0.995, d * PITCH * 0.995, 2, 0.05 * PITCH), [w, d, H]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <group position={pos} rotation={[0, rot, 0]}>
      <mesh geometry={geo} position={[0, H / 2, 0]} castShadow receiveShadow material={plastic(color)} />
      <TopStuds w={w * PITCH} d={d * PITCH} y={H} color={color} />
    </group>
  );
}

// --- suelo: placa base con mosaico ------------------------------------------------------------
const BASE_STUDS = 64;
function Baseplate() {
  const items = useMemo(() => {
    const mosaic = new Map(batMosaic(40, 24).map((m) => [`${Math.round(m.x / PITCH - 0.5)}:${Math.round(m.z / PITCH - 0.5)}`, m.color]));
    const out: StudItem[] = [];
    for (let a = 0; a < BASE_STUDS; a++)
      for (let b = 0; b < BASE_STUDS; b++) {
        const ix = a - BASE_STUDS / 2, iz = b - BASE_STUDS / 2;
        const key = `${ix}:${iz}`;
        const tone = rnd(a * 64 + b) > 0.93 ? "#2b3137" : "#23282d";
        out.push({ x: (ix + 0.5) * PITCH, y: FLOOR_Y, z: (iz + 0.5) * PITCH, color: mosaic.get(key) ?? tone });
      }
    return out;
  }, []);
  const size = BASE_STUDS * PITCH;
  return (
    <>
      <mesh position={[0, FLOOR_Y - PLATE_H / 2, 0]} receiveShadow material={plastic("#1c2126")}><boxGeometry args={[size, PLATE_H, size]} /></mesh>
      <StudInstances items={items} />
    </>
  );
}

// --- muro de ladrillos ------------------------------------------------------------------------
function Walls() {
  const bricks = useMemo(() => wallBricks(15, FLOOR_Y), []);
  const body = useRef<THREE.InstancedMesh>(null);
  const geo = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 2, 0.045), []);
  const studs = useMemo(() => {
    const out: StudItem[] = [];
    for (const b of bricks) {
      if (!b.top) continue;
      const cols = Math.round(b.len / PITCH), rows = Math.round(b.thick / PITCH);
      for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
        const lx = (i - (cols - 1) / 2) * PITCH, lz = (j - (rows - 1) / 2) * PITCH;
        out.push({ x: b.x + Math.cos(b.rot) * lx + Math.sin(b.rot) * lz, z: b.z - Math.sin(b.rot) * lx + Math.cos(b.rot) * lz, y: b.y + b.h / 2, color: b.color });
      }
    }
    return out;
  }, [bricks]);
  useLayoutEffect(() => {
    const m = body.current;
    if (!m) return;
    const d = new THREE.Object3D();
    const c = new THREE.Color();
    bricks.forEach((b, i) => {
      d.position.set(b.x, b.y, b.z);
      d.rotation.set(0, b.rot, 0);
      d.scale.set(b.len, b.h, b.thick);
      d.updateMatrix();
      m.setMatrixAt(i, d.matrix);
      m.setColorAt(i, c.set(b.color));
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [bricks]);
  return (
    <>
      <instancedMesh ref={body} args={[geo, undefined, bricks.length]} castShadow receiveShadow material={plastic("#ffffff")} />
      <StudInstances items={studs} />
    </>
  );
}

// --- pantallas y mobiliario -------------------------------------------------------------------
export function screenTexture(seed: number, tint: string, title: string): THREE.CanvasTexture {
  const ops: Op[] = [{ k: "rect", x: 0, y: 0, w: 100, h: 100, c: "#06161b" }, { k: "rect", x: 0, y: 0, w: 100, h: 15, c: tint }, { k: "text", x: 50, y: 7.5, s: title, c: "#06161b", size: 9 }];
  for (let i = 0; i < 9; i++) ops.push({ k: "rect", x: 6, y: 23 + i * 8.2, w: 16 + rnd(seed * 10 + i) * 60, h: 4, c: i % 3 === 0 ? tint : "#2a6a78" });
  ops.push({ k: "circle", x: 82, y: 70, r: 12, c: "#0e2a33" }, { k: "line", x1: 82, y1: 70, x2: 82 + 10 * Math.cos(seed), y2: 70 + 10 * Math.sin(seed), c: tint, w: 3 });
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  drawOps(c.getContext("2d") as unknown as Parameters<typeof drawOps>[0], ops, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Terminal del Bat-ordenador: base de ladrillos, pantalla inclinada y teclado de baldosas. */
function Console({ angle, radius, seed, tint, title }: { angle: number; radius: number; seed: number; tint: string; title: string }) {
  const tex = useMemo(() => screenTexture(seed, tint, title), [seed, tint, title]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[Math.cos(angle) * radius, FLOOR_Y, Math.sin(angle) * radius]} rotation={[0, -angle - Math.PI / 2, 0]}>
      <Brick w={6} d={3} h={2} color={P.darkGrey} pos={[0, 0, 0]} />
      <Brick w={6} d={1} h={1} color={P.black} pos={[0, 2 * BRICK_H, -PITCH * 0.9]} />
      <group position={[0, 2 * BRICK_H + BRICK_H * 0.6, -PITCH * 0.5]} rotation={[-0.45, 0, 0]}>
        <mesh castShadow material={plastic(P.black)}><boxGeometry args={[5.2 * PITCH, 3.1 * PITCH, 0.35 * PITCH]} /></mesh>
        <mesh position={[0, 0, 0.19 * PITCH]}><planeGeometry args={[4.8 * PITCH, 2.7 * PITCH]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>
      </group>
    </group>
  );
}

/** Pantalla gigante del Bat-ordenador sobre la pared del fondo. */
function BigScreen({ accent }: { accent: string }) {
  const tex = useMemo(() => {
    const ops: Op[] = [{ k: "rect", x: 0, y: 0, w: 100, h: 100, c: "#06100f" }, { k: "poly", pts: BAT_POLY.map(([x, y]) => [x * 0.5 + 25, y * 0.5 + 18] as [number, number]), c: accent },
      { k: "text", x: 50, y: 84, s: "CENTRO DE MANDO", c: "#9ff", size: 6 }];
    for (let i = 0; i < 5; i++) ops.push({ k: "rect", x: 4, y: 8 + i * 6, w: 10 + rnd(i + 3) * 20, h: 3, c: "#2a6a78" }, { k: "rect", x: 96 - (10 + rnd(i + 9) * 20), y: 8 + i * 6, w: 10 + rnd(i + 9) * 20, h: 3, c: "#2a6a78" });
    const c = document.createElement("canvas");
    c.width = 512; c.height = 288;
    const ctx = c.getContext("2d") as unknown as Parameters<typeof drawOps>[0];
    (ctx as unknown as CanvasRenderingContext2D).scale(512 / 256, 288 / 256);
    drawOps(ctx, ops, 256);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [accent]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[0, FLOOR_Y + 3.4, -13.2]}>
      <mesh castShadow material={plastic(P.black)}><boxGeometry args={[8.6, 4.9, 0.5]} /></mesh>
      <mesh position={[0, 0, 0.27]}><planeGeometry args={[8.1, 4.55]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>
      <TopStuds w={8.6} d={0.44} y={2.45} color={P.black} />
    </group>
  );
}

/** Batmóvil de ladrillos: chasis, cabina, aletas y ruedas. */
function Batmobile({ position, rotY }: { position: [number, number, number]; rotY: number }) {
  return (
    <group position={position} rotation={[0, rotY, 0]}>
      <Brick w={8} d={3} h={1} color={P.black} pos={[0, 0.25, 0]} />
      <Brick w={4} d={2} h={1} color={P.darkGrey} pos={[-0.4, 0.25 + BRICK_H, 0]} />
      <mesh position={[-0.4, 0.25 + 2 * BRICK_H + 0.04, 0]} material={plastic("#0b3a52")}><boxGeometry args={[1.5, 0.12, 0.7]} /></mesh>
      <Brick w={2} d={3} h={1} color={P.black} pos={[1.5, 0.25 + BRICK_H, 0]} />
      {[-1, 1].map((s) => <mesh key={s} position={[-1.9, 0.25 + 1.6 * BRICK_H, s * 0.5]} rotation={[0, 0, -0.5]} castShadow material={plastic(P.black)}><boxGeometry args={[1.0, 0.07, 0.26]} /></mesh>)}
      {[[-1.2, 1], [-1.2, -1], [1.2, 1], [1.2, -1]].map(([x, z], i) => (
        <group key={i} position={[x, 0.3, z * 0.75]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh castShadow material={plastic(P.black)}><cylinderGeometry args={[0.3, 0.3, 0.26, 24]} /></mesh>
          <mesh position={[0, z * 0.14, 0]} material={plastic(P.grey)}><cylinderGeometry args={[0.15, 0.15, 0.03, 16]} /></mesh>
        </group>
      ))}
      <mesh position={[2.0, 0.28, 0]} material={plastic(P.yellow)}><boxGeometry args={[0.07, 0.07, 0.8]} /></mesh>
    </group>
  );
}

/** Montón de ladrillos sueltos. */
function BrickPile({ position, colors }: { position: [number, number, number]; colors: string[] }) {
  return (
    <group position={position}>
      {colors.map((c, i) => <Brick key={i} w={4} d={2} color={c} pos={[(i % 2) * 0.25, i * BRICK_H, 0]} rot={i * 0.45} />)}
    </group>
  );
}

/** Moneda gigante (trofeo clásico de la Batcueva). */
function GiantPenny({ position }: { position: [number, number, number] }) {
  return (
    <group position={position} rotation={[0, 0.5, 0]}>
      <mesh rotation={[Math.PI / 2 - 0.12, 0, 0]} position={[0, 1.4, 0]} castShadow material={plastic("#B0743A")}><cylinderGeometry args={[1.4, 1.4, 0.2, 40]} /></mesh>
      <mesh rotation={[Math.PI / 2 - 0.12, 0, 0]} position={[0, 1.4, 0.115]} material={plastic("#D09168")}><cylinderGeometry args={[1.05, 1.05, 0.02, 40]} /></mesh>
    </group>
  );
}

/** Luces de estudio procedurales para los reflejos del plástico (sin descargar nada). Van dentro de <Environment>. */
export function StudioLights() {
  return (
    <>
      <Lightformer form="rect" intensity={2.4} position={[0, 9, 4]} scale={[14, 4, 1]} rotation-x={Math.PI / 2} />
      <Lightformer form="rect" intensity={1.3} position={[-8, 4, 6]} scale={[6, 6, 1]} />
      <Lightformer form="rect" intensity={1.0} position={[8, 3, -6]} scale={[6, 6, 1]} color="#7dd3fc" />
      <Lightformer form="ring" intensity={1.6} position={[0, 6, -8]} scale={4} color="#ffd54a" />
    </>
  );
}

/** Placa redonda con tacos sobre la que se sitúa cada personaje (4×4 con 12 tacos; la del jefe, 6×6). */
export function Plate({ position, color, big = false }: { position: [number, number, number]; color: string; big?: boolean }) {
  const r = plateRadius(big);
  const items = useMemo(() => roundPlateStuds(big ? 3 : 2).map(([x, z]) => ({ x, y: PLATE_H, z, color })), [big, color]);
  return (
    <group position={position}>
      <mesh position={[0, PLATE_H / 2, 0]} castShadow receiveShadow material={plastic(color)}><cylinderGeometry args={[r, r, PLATE_H, 48]} /></mesh>
      <StudInstances items={items} />
    </group>
  );
}

export function Batcave({ accent }: { accent: string }) {
  const signal = useMemo(() => {
    const ops: Op[] = [{ k: "circle", x: 50, y: 50, r: 48, c: accent }, { k: "poly", pts: BAT_POLY, c: "#05131D" }];
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    drawOps(c.getContext("2d") as unknown as Parameters<typeof drawOps>[0], ops, 256);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [accent]);
  useEffect(() => () => signal.dispose(), [signal]);
  return (
    <>
      <fog attach="fog" args={["#05070b", 18, 42]} />
      <Baseplate />
      <Walls />
      <BigScreen accent={accent} />
      {[-2.55, -2.1, -1.65, -1.2, -0.75].map((a, i) => (
        <Console key={i} angle={a} radius={11.5} seed={i + 1} tint={i % 2 ? "#4ade80" : "#22d3ee"} title={["ALERTA", "GOTHAM", "RED", "ANÁLISIS", "ARCHIVO"][i]} />
      ))}
      <Batmobile position={[-9.2, FLOOR_Y, 5.2]} rotY={0.75} />
      <BrickPile position={[9.5, FLOOR_Y, 7]} colors={[P.yellow, P.black, P.blue, P.red]} />
      <BrickPile position={[-5, FLOOR_Y, 10.5]} colors={[P.grey, P.yellow, P.black]} />
      <GiantPenny position={[10, FLOOR_Y, -3]} />
      {/* proyector de la señal del murciélago */}
      <group position={[0, 11.5, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={plastic(P.darkGrey)}><cylinderGeometry args={[1.5, 1.5, 0.3, 40]} /></mesh>
        <mesh position={[0, -0.2, 0]} rotation={[Math.PI / 2, 0, 0]}><circleGeometry args={[1.35, 40]} /><meshBasicMaterial map={signal} toneMapped={false} side={THREE.DoubleSide} /></mesh>
      </group>
      <mesh position={[0, 5, 0]}><coneGeometry args={[3.2, 13, 48, 1, true]} /><meshBasicMaterial color={accent} transparent opacity={0.06} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      <Sparkles count={70} scale={[11, 7, 11]} position={[0, 2.5, 0]} size={2.4} speed={0.25} opacity={0.5} color={accent} />
    </>
  );
}
