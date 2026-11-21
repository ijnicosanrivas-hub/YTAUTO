/**
 * Batcueva (último videojuego LEGO Batman): cueva de roca oscura con luz azulada, dos túneles con arcos de acero,
 * centro de mando con la gran pantalla del murciélago, pilares, consolas, suelo metálico y, en el centro, una
 * plataforma de exposición de tacos LEGO con las figuras sobre bases negras y placas de nombre.
 */
import { Lightformer, Sparkles } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { BRICK_H, PITCH, PLATE_H, rnd } from "./bricks";
import { plastic } from "./Minifig";
import { BAT_POLY, drawOps, type Op } from "./ops";
import { LDU, STUD } from "./styleBible";

export const FLOOR_Y = -1.6;
export { PLATE_H };
/** Radio de la base negra de cada personaje: 4×4 tacos; la del jefe, 6×6. */
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

export function StudInstances({ items }: { items: StudItem[] }) {
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

/** Ladrillo suelto (cuerpo biselado + tacos). Dimensiones en tacos y alturas de ladrillo. */
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

// --- texturas procedurales --------------------------------------------------------------------
export function canvasTex(w: number, h: number, draw: (c: CanvasRenderingContext2D) => void, srgb = true): THREE.CanvasTexture {
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  draw(cv.getContext("2d")!);
  const t = new THREE.CanvasTexture(cv);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export function screenTexture(seed: number, tint: string, title: string): THREE.CanvasTexture {
  const ops: Op[] = [{ k: "rect", x: 0, y: 0, w: 100, h: 100, c: "#06161b" }, { k: "rect", x: 0, y: 0, w: 100, h: 14, c: tint }, { k: "text", x: 50, y: 7, s: title, c: "#06161b", size: 9 }];
  for (let i = 0; i < 9; i++) ops.push({ k: "rect", x: 6, y: 22 + i * 8.4, w: 18 + rnd(seed * 10 + i) * 62, h: 4, c: i % 3 === 0 ? tint : "#2a6a78" });
  ops.push({ k: "circle", x: 82, y: 70, r: 12, c: "#0e2a33" }, { k: "line", x1: 82, y1: 70, x2: 82 + 10 * Math.cos(seed), y2: 70 + 10 * Math.sin(seed), c: tint, w: 3 });
  return canvasTex(256, 256, (c) => drawOps(c as unknown as Parameters<typeof drawOps>[0], ops, 256));
}

/** Pantalla principal: interfaz cian con el emblema del murciélago amarillo. */
function mainScreenTexture(accent: string): THREE.CanvasTexture {
  return canvasTex(1024, 540, (c) => {
    c.fillStyle = "#04141c"; c.fillRect(0, 0, 1024, 540);
    c.strokeStyle = "rgba(60,200,230,0.55)"; c.lineWidth = 3;
    c.strokeRect(14, 14, 996, 512);
    for (let i = 0; i < 14; i++) { c.beginPath(); c.moveTo(14, 40 + i * 36); c.lineTo(1010, 40 + i * 36); c.strokeStyle = "rgba(60,200,230,0.07)"; c.lineWidth = 1; c.stroke(); }
    c.fillStyle = "rgba(60,200,230,0.8)";
    for (let i = 0; i < 7; i++) { c.fillRect(34, 44 + i * 22, 60 + rnd(i + 3) * 150, 8); c.fillRect(990 - (60 + rnd(i + 9) * 150), 44 + i * 22, 60 + rnd(i + 9) * 150, 8); }
    c.save(); c.translate(512, 270); c.scale(5.2, 4.2);
    c.beginPath(); c.ellipse(0, 0, 40, 25, 0, 0, Math.PI * 2); c.fillStyle = accent; c.fill();
    c.lineWidth = 1.4; c.strokeStyle = "#05131D"; c.stroke();
    c.beginPath(); BAT_POLY.forEach(([x, y], i) => { const px = (x - 50) * 0.7, py = (y - 45) * 0.7; if (i) c.lineTo(px, py); else c.moveTo(px, py); }); c.closePath(); c.fillStyle = "#05131D"; c.fill();
    c.restore();
    c.fillStyle = "rgba(60,200,230,0.9)"; c.font = "bold 26px Impact, sans-serif"; c.textAlign = "center"; c.fillText("CENTRO DE MANDO · BATCUEVA", 512, 508);
  });
}

function floorTexture(): THREE.CanvasTexture {
  const t = canvasTex(1024, 1024, (c) => {
    c.fillStyle = "#1c232a"; c.fillRect(0, 0, 1024, 1024);
    for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) {
      const v = 26 + Math.floor(rnd(i * 8 + j) * 10);
      c.fillStyle = `rgb(${v},${v + 6},${v + 12})`; c.fillRect(i * 128 + 3, j * 128 + 3, 122, 122);
      c.fillStyle = "rgba(255,255,255,0.05)"; c.fillRect(i * 128 + 3, j * 128 + 3, 122, 3);
      c.fillStyle = "#0a0e12";
      for (const [dx, dy] of [[12, 12], [116, 12], [12, 116], [116, 116]]) { c.beginPath(); c.arc(i * 128 + dx, j * 128 + dy, 4, 0, Math.PI * 2); c.fill(); }
    }
  });
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(10, 10);
  return t;
}

function gratingTexture(): THREE.CanvasTexture {
  const t = canvasTex(256, 256, (c) => {
    c.fillStyle = "#10161b"; c.fillRect(0, 0, 256, 256);
    c.strokeStyle = "#2c3640"; c.lineWidth = 4;
    for (let i = 0; i <= 256; i += 16) { c.beginPath(); c.moveTo(i, 0); c.lineTo(i, 256); c.stroke(); c.beginPath(); c.moveTo(0, i); c.lineTo(256, i); c.stroke(); }
  });
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(9, 3);
  return t;
}

// --- cueva: roca y estalactitas ---------------------------------------------------------------
const ROCK_TONES = ["#14181c", "#1b2025", "#23292f", "#101417", "#1a2026"];

function Rocks() {
  const ref = useRef<THREE.InstancedMesh>(null);
  const stal = useRef<THREE.InstancedMesh>(null);
  const N = 120, M = 52;
  useLayoutEffect(() => {
    const d = new THREE.Object3D();
    const c = new THREE.Color();
    const m = ref.current;
    if (m) {
      let n = 0;
      for (let i = 0; n < N && i < N * 2; i++) {
        const a = (i / (N * 2)) * Math.PI * 2 + rnd(i) * 0.05;
        if (Math.abs(Math.sin(a)) < 0.26) continue; // se deja libre la roca detrás de los túneles (ángulos 0 y π)
        if (Math.sin(a) > 0.2) continue; // y la del lado de la cámara (delante de la sala): la cueva se ve desde dentro
        const r = 31 + rnd(i + 31) * 7;
        const sx = 3.6 + rnd(i + 7) * 3.8, sy = 3 + rnd(i + 13) * 7.5;
        d.position.set(Math.cos(a) * r, FLOOR_Y + sy * 0.55 + rnd(i + 3) * 2, Math.sin(a) * r);
        d.rotation.set(rnd(i + 21) * 3, rnd(i + 22) * 3, rnd(i + 23) * 3);
        d.scale.set(sx, sy, sx);
        d.updateMatrix();
        m.setMatrixAt(n, d.matrix);
        m.setColorAt(n, c.set(ROCK_TONES[Math.floor(rnd(i + 41) * ROCK_TONES.length)]));
        n++;
      }
      m.count = n;
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
    }
    const s = stal.current;
    if (s) {
      for (let i = 0; i < M; i++) {
        const a = rnd(i * 3) * Math.PI * 2, r = 6 + rnd(i * 3 + 1) * 17;
        const h = 4 + rnd(i * 3 + 2) * 6;
        d.position.set(Math.cos(a) * r, FLOOR_Y + 19 - h / 2, Math.sin(a) * r);
        d.rotation.set(Math.PI, 0, 0);
        d.scale.set(1.2 + rnd(i + 90) * 1.6, h, 1.2 + rnd(i + 91) * 1.6);
        d.updateMatrix();
        s.setMatrixAt(i, d.matrix);
        s.setColorAt(i, c.set(ROCK_TONES[i % ROCK_TONES.length]));
      }
      s.instanceMatrix.needsUpdate = true;
      if (s.instanceColor) s.instanceColor.needsUpdate = true;
    }
  }, []);
  return (
    <>
      <instancedMesh ref={ref} args={[undefined, undefined, N]} receiveShadow castShadow frustumCulled={false}>
        <dodecahedronGeometry args={[1, 0]} />
        <meshStandardMaterial color="#ffffff" roughness={0.95} flatShading />
      </instancedMesh>
      <instancedMesh ref={stal} args={[undefined, undefined, M]} frustumCulled={false}>
        <coneGeometry args={[1, 1, 6]} />
        <meshStandardMaterial color="#ffffff" roughness={0.95} flatShading />
      </instancedMesh>
    </>
  );
}

// --- túneles con arco de acero -----------------------------------------------------------------
function Tunnel({ side }: { side: -1 | 1 }) {
  const steel = plastic("#4b545e");
  const dark = plastic("#262d34");
  return (
    <group position={[side * 14.6, FLOOR_Y, -9.5]} rotation={[0, side < 0 ? Math.PI / 2 - 0.5 : -(Math.PI / 2 - 0.5), 0]}>
      <mesh position={[0, 4, 0]} castShadow material={steel}><torusGeometry args={[4.5, 0.55, 10, 32, Math.PI]} /></mesh>
      {[1, 2, 3, 4].map((i) => <mesh key={i} position={[0, 4, -i * 0.95]} castShadow material={dark}><torusGeometry args={[4.3 - i * 0.12, 0.28, 8, 28, Math.PI]} /></mesh>)}
      {[-4.5, 4.5].map((x) => (
        <group key={x}>
          <mesh position={[x, 2, 0]} castShadow material={steel}><boxGeometry args={[1.1, 4, 1.5]} /></mesh>
          {[0.8, 1.6, 2.4, 3.2].map((y) => <mesh key={y} position={[x * 1.02, y, 0.78]}><boxGeometry args={[0.6, 0.12, 0.05]} /><meshBasicMaterial color={new THREE.Color(0.6, 1.6, 2)} toneMapped={false} /></mesh>)}
        </group>
      ))}
      <mesh position={[0, 4, -4.4]}><planeGeometry args={[10, 9]} /><meshBasicMaterial color="#010304" /></mesh>
      {side > 0 && <mesh position={[1.5, 1.6, -4.3]}><circleGeometry args={[3.4, 24]} /><meshBasicMaterial color="#c0731c" transparent opacity={0.35} depthWrite={false} /></mesh>}
      <mesh position={[0, 9.4, 0.6]}><boxGeometry args={[4.6, 0.16, 0.6]} /><meshBasicMaterial color={new THREE.Color(2.6, 2.6, 2.6)} toneMapped={false} /></mesh>
    </group>
  );
}

// --- centro de mando ---------------------------------------------------------------------------
function Monitor({ x, y, w, h, tex, tilt = 0 }: { x: number; y: number; w: number; h: number; tex: THREE.Texture; tilt?: number }) {
  return (
    <group position={[x, y, 0]} rotation={[tilt, 0, 0]}>
      <mesh castShadow material={plastic("#0b0f13")}><boxGeometry args={[w + 0.3, h + 0.3, 0.22]} /></mesh>
      <mesh position={[0, 0, 0.12]}><planeGeometry args={[w, h]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>
    </group>
  );
}

function CommandCenter({ accent }: { accent: string }) {
  const main = useMemo(() => mainScreenTexture(accent), [accent]);
  const small = useMemo(() => [screenTexture(1, "#22d3ee", "ALERTA"), screenTexture(2, "#4ade80", "RED"), screenTexture(3, "#22d3ee", "ANÁLISIS"), screenTexture(4, "#4ade80", "ARCHIVO")], []);
  const grate = useMemo(gratingTexture, []);
  useEffect(() => () => { main.dispose(); small.forEach((t) => t.dispose()); grate.dispose(); }, [main, small, grate]);
  return (
    <group position={[0, FLOOR_Y, -15]}>
      <mesh position={[0, 0.22, 0]} receiveShadow><boxGeometry args={[27, 0.44, 8]} /><meshStandardMaterial map={grate} color="#aab4bf" roughness={0.5} metalness={0.6} /></mesh>
      <mesh position={[0, 6, -3.6]} castShadow material={plastic("#10151a")}><boxGeometry args={[27, 13, 0.6]} /></mesh>
      {Array.from({ length: 10 }, (_, i) => <mesh key={i} position={[-12 + i * 2.7, 1.5, 3.9]} castShadow material={plastic("#4b545e")}><boxGeometry args={[0.1, 1.2, 0.1]} /></mesh>)}
      <mesh position={[0, 2.05, 3.9]} material={plastic("#4b545e")}><boxGeometry args={[26.4, 0.1, 0.1]} /></mesh>
      <group position={[0, 0, -3.1]}>
        <group position={[0, 5.4, 0]}><Monitor x={0} y={0} w={7.6} h={4} tex={main} /></group>
        <Monitor x={-5.8} y={6.4} w={2.8} h={1.8} tex={small[0]} />
        <Monitor x={-5.8} y={4.2} w={2.8} h={1.8} tex={small[1]} />
        <Monitor x={5.8} y={6.4} w={2.8} h={1.8} tex={small[2]} />
        <Monitor x={5.8} y={4.2} w={2.8} h={1.8} tex={small[3]} />
        <Monitor x={-1.7} y={8.6} w={2.4} h={1.4} tex={small[1]} />
        <Monitor x={1.7} y={8.6} w={2.4} h={1.4} tex={small[0]} />
      </group>
      {[-9.4, 9.4].map((x) => (
        <group key={x} position={[x, 0, -2.6]}>
          <mesh position={[0, 5.2, 0]} castShadow material={plastic("#303944")}><boxGeometry args={[1.5, 10.4, 1.5]} /></mesh>
          <mesh position={[0, 10.5, 0]} castShadow material={plastic("#232b33")}><boxGeometry args={[2, 0.5, 2]} /></mesh>
          {[2, 3.4, 4.8, 6.2, 7.6].map((y) => <mesh key={y} position={[0, y, 0.78]}><boxGeometry args={[0.9, 0.16, 0.04]} /><meshBasicMaterial color={new THREE.Color(0.5, 1.6, 2.2)} toneMapped={false} /></mesh>)}
        </group>
      ))}
    </group>
  );
}

/** Luces de estudio procedurales para los reflejos del plástico y el acero (sin descargar nada). Van dentro de <Environment>. */
export function StudioLights() {
  return (
    <>
      <Lightformer form="rect" intensity={2.2} position={[0, 10, 4]} scale={[14, 4, 1]} rotation-x={Math.PI / 2} color="#dff3fa" />
      <Lightformer form="rect" intensity={1.5} position={[-9, 4, 6]} scale={[6, 6, 1]} color="#6fd3ea" />
      <Lightformer form="rect" intensity={1.0} position={[9, 3, -6]} scale={[6, 6, 1]} color="#ffd9a0" />
    </>
  );
}

function NamePlate({ label, z }: { label: string; z: number }) {
  const tex = useMemo(() => canvasTex(256, 64, (c) => {
    c.fillStyle = "#b9bec4"; c.fillRect(0, 0, 256, 64);
    c.fillStyle = "#16191d"; c.font = "bold 30px Impact, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillText(label.toUpperCase(), 128, 34, 236);
  }), [label]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[0, 0.06, z]} rotation={[-0.35, 0, 0]}>
      <mesh castShadow material={plastic("#9aa0a6")}><boxGeometry args={[1.5, 0.12, 0.42]} /></mesh>
      <mesh position={[0, 0.065, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[1.42, 0.36]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>
    </group>
  );
}

/** Base negra redonda de cada personaje, con su placa de nombre delante (el aro de color es el del personaje). */
export function Base({ position, color, big = false, label = "" }: { position: [number, number, number]; color: string; big?: boolean; label?: string }) {
  const r = plateRadius(big);
  return (
    <group position={position}>
      <mesh position={[0, PLATE_H / 2, 0]} castShadow receiveShadow material={plastic("#0d1014")}><cylinderGeometry args={[r, r, PLATE_H, 48]} /></mesh>
      <mesh position={[0, PLATE_H + 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[r - 0.2, r - 0.1, 48]} /><meshBasicMaterial color={color} /></mesh>
      {label && <NamePlate label={label} z={r + 0.62} />}
    </group>
  );
}

export function Batcave({ accent }: { accent: string }) {
  const floor = useMemo(floorTexture, []);
  useEffect(() => () => floor.dispose(), [floor]);
  return (
    <>
      <fog attach="fog" args={["#05090d", 38, 120]} />
      <pointLight position={[-14, 7, -4]} color="#3fc6e0" intensity={70} distance={28} />
      <pointLight position={[14, 6, -3]} color="#f0a53a" intensity={34} distance={22} />
      <pointLight position={[0, 9, -10]} color="#7fdcf0" intensity={40} distance={22} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y - 0.62, 0]} receiveShadow>
        <planeGeometry args={[70, 70]} />
        <meshStandardMaterial map={floor} roughness={0.42} metalness={0.55} />
      </mesh>
      <Rocks />
      <Tunnel side={-1} />
      <Tunnel side={1} />
      <CommandCenter accent={accent} />
      <Sparkles count={60} scale={[16, 8, 14]} position={[0, 3, -2]} size={2.2} speed={0.2} opacity={0.4} color="#8fdcf0" />
    </>
  );
}
