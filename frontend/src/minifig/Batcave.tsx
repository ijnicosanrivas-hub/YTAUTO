/** Batcueva construida con tacos y plásticos LEGO (mismo material y paleta que las figuras). */
import { Lightformer } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { drawOps, type Op } from "./ops";
import { plastic } from "./Minifig";
import { PLASTIC as P } from "./styleBible";

export const FLOOR_Y = -1.6;
export const PLATE_H = 0.14;

const rnd = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x); // pseudoaleatorio determinista (la sala es idéntica en cada carga)
};

/** Cuadrícula de tacos instanciados. */
function Studs({ cols, rows, pitch, r = 0.2, h = 0.08, color, y }: { cols: number; rows: number; pitch: number; r?: number; h?: number; color: string; y: number }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const d = new THREE.Object3D();
    let i = 0;
    for (let a = 0; a < cols; a++)
      for (let b = 0; b < rows; b++) {
        d.position.set((a - (cols - 1) / 2) * pitch, y, (b - (rows - 1) / 2) * pitch);
        d.updateMatrix();
        m.setMatrixAt(i++, d.matrix);
      }
    m.instanceMatrix.needsUpdate = true;
  }, [cols, rows, pitch, y]);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, cols * rows]} material={plastic(color)} receiveShadow>
      <cylinderGeometry args={[r, r, h, 14]} />
    </instancedMesh>
  );
}

function screenTexture(seed: number, tint: string, title: string): THREE.CanvasTexture {
  const ops: Op[] = [{ k: "rect", x: 0, y: 0, w: 100, h: 100, c: "#071318" }, { k: "rect", x: 0, y: 0, w: 100, h: 14, c: tint }, { k: "text", x: 50, y: 7, s: title, c: "#071318", size: 9 }];
  for (let i = 0; i < 9; i++) {
    const w = 18 + rnd(seed * 10 + i) * 62;
    ops.push({ k: "rect", x: 6, y: 22 + i * 8.4, w, h: 4, c: i % 3 === 0 ? tint : "#2a6a78" });
  }
  ops.push({ k: "circle", x: 82, y: 70, r: 12, c: "#0e2a33" }, { k: "line", x1: 82, y1: 70, x2: 82 + 10 * Math.cos(seed), y2: 70 + 10 * Math.sin(seed), c: tint, w: 3 });
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  drawOps(c.getContext("2d") as unknown as Parameters<typeof drawOps>[0], ops, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function Console({ angle, radius, seed, tint, title }: { angle: number; radius: number; seed: number; tint: string; title: string }) {
  const tex = useMemo(() => screenTexture(seed, tint, title), [seed, tint, title]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[Math.cos(angle) * radius, FLOOR_Y, Math.sin(angle) * radius]} rotation={[0, -angle - Math.PI / 2, 0]}>
      <mesh position={[0, 0.45, 0]} castShadow material={plastic(P.darkGrey)}><boxGeometry args={[2.4, 0.9, 1]} /></mesh>
      <mesh position={[0, 1.15, -0.1]} rotation={[-0.35, 0, 0]} castShadow material={plastic(P.black)}><boxGeometry args={[2.3, 1.4, 0.12]} /></mesh>
      <mesh position={[0, 1.16, -0.03]} rotation={[-0.35, 0, 0]}>
        <planeGeometry args={[2.1, 1.2]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
      <Studs cols={8} rows={2} pitch={0.28} r={0.07} h={0.04} color={P.grey} y={0.92} />
    </group>
  );
}

function Batmobile({ position, rotY }: { position: [number, number, number]; rotY: number }) {
  return (
    <group position={position} rotation={[0, rotY, 0]}>
      <mesh position={[0, 0.35, 0]} castShadow material={plastic(P.black)}><boxGeometry args={[3.2, 0.4, 1.3]} /></mesh>
      <mesh position={[-0.2, 0.7, 0]} castShadow material={plastic(P.darkGrey)}><boxGeometry args={[1.5, 0.35, 0.9]} /></mesh>
      <mesh position={[-0.2, 0.9, 0]} material={plastic("#3b6e86")}><boxGeometry args={[1.1, 0.12, 0.7]} /></mesh>
      <mesh position={[1.7, 0.32, 0]} castShadow material={plastic(P.black)}><boxGeometry args={[0.5, 0.18, 0.7]} /></mesh>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[-1.55, 0.85, s * 0.45]} rotation={[0, 0, -0.5]} castShadow material={plastic(P.black)}><boxGeometry args={[0.9, 0.08, 0.28]} /></mesh>
      ))}
      {[[-1.05, 1], [-1.05, -1], [1.05, 1], [1.05, -1]].map(([x, z], i) => (
        <group key={i} position={[x, 0.3, z * 0.72]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh castShadow material={plastic(P.darkGrey)}><cylinderGeometry args={[0.32, 0.32, 0.24, 20]} /></mesh>
          <mesh position={[0, z * 0.13, 0]} material={plastic(P.grey)}><cylinderGeometry args={[0.15, 0.15, 0.02, 14]} /></mesh>
        </group>
      ))}
      <mesh position={[1.35, 0.4, 0]} material={plastic(P.yellow)}><boxGeometry args={[0.08, 0.08, 0.9]} /></mesh>
    </group>
  );
}

/** Roca de la cueva: columnas de ladrillos oscuros de distintas alturas (instanciadas). */
function Walls() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const N = 72;
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const d = new THREE.Object3D();
    const col = new THREE.Color();
    const tones = ["#1c2029", "#252a35", "#2d3340", "#171a22"];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const h = 4 + rnd(i) * 9;
      const rad = 21 + rnd(i + 99) * 3;
      d.position.set(Math.cos(a) * rad, FLOOR_Y + h / 2, Math.sin(a) * rad);
      d.rotation.set(0, -a, 0);
      d.scale.set(2.4 + rnd(i + 7) * 1.4, h, 2.6);
      d.updateMatrix();
      m.setMatrixAt(i, d.matrix);
      m.setColorAt(i, col.set(tones[i % tones.length]));
    }
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, []);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, N]} receiveShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshPhysicalMaterial {...{ roughness: 0.55, metalness: 0, clearcoat: 0.3 }} color="#ffffff" />
    </instancedMesh>
  );
}

function BrickPile({ position, colors }: { position: [number, number, number]; colors: string[] }) {
  return (
    <group position={position}>
      {colors.map((c, i) => (
        <group key={i} position={[(i % 2) * 0.15, i * 0.32, (i % 2) * -0.1]} rotation={[0, i * 0.4, 0]}>
          <mesh castShadow material={plastic(c)}><boxGeometry args={[1.0, 0.32, 0.5]} /></mesh>
          {[-0.3, 0, 0.3].map((x) => [-0.12, 0.12].map((z) => (
            <mesh key={`${x}${z}`} position={[x, 0.19, z]} material={plastic(c)}><cylinderGeometry args={[0.07, 0.07, 0.07, 12]} /></mesh>
          )))}
        </group>
      ))}
    </group>
  );
}

/** Placa redonda con tacos sobre la que se sitúa cada personaje (color = el del personaje). */
export function Plate({ position, color, big = false }: { position: [number, number, number]; color: string; big?: boolean }) {
  const r = big ? 1.1 : 0.82;
  const ring = big ? 12 : 8;
  return (
    <group position={position}>
      <mesh position={[0, PLATE_H / 2, 0]} castShadow receiveShadow material={plastic(color)}>
        <cylinderGeometry args={[r, r, PLATE_H, 36]} />
      </mesh>
      {Array.from({ length: ring }, (_, i) => (
        <mesh key={i} position={[Math.cos((i / ring) * Math.PI * 2) * (r - 0.18), PLATE_H + 0.03, Math.sin((i / ring) * Math.PI * 2) * (r - 0.18)]} material={plastic(color)}>
          <cylinderGeometry args={[0.07, 0.07, 0.06, 12]} />
        </mesh>
      ))}
    </group>
  );
}

/** Luces de estudio procedurales para los reflejos del plástico (sin descargar nada). Van dentro de <Environment>. */
export function StudioLights() {
  return (
    <>
      <Lightformer form="rect" intensity={2.2} position={[0, 9, 4]} scale={[14, 4, 1]} rotation-x={Math.PI / 2} />
      <Lightformer form="rect" intensity={1.2} position={[-8, 4, 6]} scale={[6, 6, 1]} />
      <Lightformer form="rect" intensity={0.9} position={[8, 3, -6]} scale={[6, 6, 1]} color="#7dd3fc" />
    </>
  );
}

export function Batcave({ accent }: { accent: string }) {
  const signal = useMemo(() => {
    const ops: Op[] = [
      { k: "circle", x: 50, y: 50, r: 48, c: accent },
      { k: "poly", pts: [[18, 42], [34, 36], [42, 30], [46, 35], [50, 27], [54, 35], [58, 30], [66, 36], [82, 42], [72, 54], [64, 47], [56, 58], [50, 53], [44, 58], [36, 47], [28, 54]], c: "#111" },
    ];
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
      {/* suelo: placa base con tacos */}
      <mesh position={[0, FLOOR_Y - 0.05, 0]} receiveShadow material={plastic("#262a35")}>
        <boxGeometry args={[30, 0.1, 30]} />
      </mesh>
      <Studs cols={36} rows={36} pitch={0.8} color="#2e3340" y={FLOOR_Y + 0.04} />
      <Walls />
      {/* ordenadores (Bat-ordenador) */}
      {[-2.4, -1.9, -1.4, -0.9, -0.4].map((a, i) => (
        <Console key={i} angle={a} radius={14} seed={i + 1} tint={i % 2 ? "#4ade80" : "#22d3ee"} title={["ALERTA", "GOTHAM", "RED", "ANÁLISIS", "ARCHIVO"][i]} />
      ))}
      <Batmobile position={[-12, FLOOR_Y, 6]} rotY={0.7} />
      <BrickPile position={[11, FLOOR_Y, 8]} colors={[P.yellow, P.black, P.blue, P.red]} />
      <BrickPile position={[-6, FLOOR_Y, 12]} colors={[P.grey, P.yellow, P.black]} />
      {/* proyector de la señal del murciélago */}
      <group position={[0, 11.5, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} material={plastic(P.darkGrey)}><cylinderGeometry args={[1.5, 1.5, 0.3, 32]} /></mesh>
        <mesh position={[0, -0.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[1.35, 32]} />
          <meshBasicMaterial map={signal} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
      </group>
      <mesh position={[0, 5, 0]}>
        <coneGeometry args={[3.2, 13, 40, 1, true]} />
        <meshBasicMaterial color={accent} transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </>
  );
}
