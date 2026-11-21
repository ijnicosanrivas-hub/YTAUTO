/**
 * Hub de la Batcueva (fábrica de IA): una instalación del videojuego por agente, todas animadas con el estado REAL
 * del agente (la pantalla se enciende, el brazo trabaja, el saco se mueve…), más el ambiente (murciélagos, holograma).
 */
import { Line, Sparkles } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Brick, FLOOR_Y, StudInstances, canvasTex, screenTexture } from "./Batcave";
import { ellipseStuds, rnd } from "./bricks";
import { HUB, HUB_SCALE, facingYaw, localToWorld } from "./hub";
import { plastic } from "./Minifig";
import { BAT_POLY } from "./ops";
import { PLASTIC as P } from "./styleBible";
import type { AgentState } from "../types";

const glow = (c: string, k = 2) => new THREE.Color(c).multiplyScalar(k);

function batGeometry(k = 0.045, depth = 0.22): THREE.ExtrudeGeometry {
  const sh = new THREE.Shape();
  BAT_POLY.forEach(([x, y], i) => (i ? sh.lineTo((x - 50) * k, (45 - y) * k) : sh.moveTo((x - 50) * k, (45 - y) * k)));
  sh.closePath();
  const g = new THREE.ExtrudeGeometry(sh, { depth, bevelEnabled: false });
  g.translate(0, 0, -depth / 2);
  return g;
}

interface Props { active: boolean; color: string }

// --- Batcomputer (Batman) ----------------------------------------------------------------------
function Batcomputer({ active }: Props) {
  const holo = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);
  const ring2 = useRef<THREE.Mesh>(null);
  const bat = useMemo(() => batGeometry(0.034), []);
  const tex = useMemo(() => screenTexture(7, "#22d3ee", "BATCOMPUTER"), []);
  useEffect(() => () => { bat.dispose(); tex.dispose(); }, [bat, tex]);
  useFrame((_, dt) => {
    if (holo.current) holo.current.rotation.y += dt * (active ? 1.8 : 0.55);
    if (ring.current) ring.current.rotation.x += dt * (active ? 2.2 : 0.5);
    if (ring2.current) ring2.current.rotation.z -= dt * (active ? 1.7 : 0.4);
  });
  return (
    <group position={[0, 0, -2.6]}>
      <mesh position={[0, 0.55, 0]} castShadow material={plastic("#232b33")}><boxGeometry args={[3.2, 1.1, 1.1]} /></mesh>
      {[-1, 1].map((sx) => (
        <group key={sx} position={[sx * 2.4, 0, 0.5]} rotation={[0, -sx * 0.6, 0]}>
          <mesh position={[0, 0.55, 0]} castShadow material={plastic("#232b33")}><boxGeometry args={[2.2, 1.1, 1]} /></mesh>
          <mesh position={[0, 1.18, 0.1]} rotation={[-0.5, 0, 0]}><planeGeometry args={[1.9, 0.8]} /><meshBasicMaterial map={tex} toneMapped={false} color={active ? "#ffffff" : "#5d7480"} /></mesh>
        </group>
      ))}
      <mesh position={[0, 1.25, 0.05]} rotation={[-0.45, 0, 0]}><planeGeometry args={[2.8, 0.9]} /><meshBasicMaterial map={tex} toneMapped={false} color={active ? "#ffffff" : "#5d7480"} /></mesh>
      <group ref={holo} position={[0, 3.3, 0]}>
        <mesh geometry={bat}><meshBasicMaterial color={glow("#22d3ee", active ? 2.6 : 1.3)} transparent opacity={0.55} toneMapped={false} depthWrite={false} /></mesh>
      </group>
      <mesh ref={ring} position={[0, 3.3, 0]}><torusGeometry args={[0.95, 0.02, 8, 64]} /><meshBasicMaterial color={glow("#22d3ee", 2)} toneMapped={false} /></mesh>
      <mesh ref={ring2} position={[0, 3.3, 0]}><torusGeometry args={[1.2, 0.015, 8, 64]} /><meshBasicMaterial color={glow("#ffd400", 1.6)} toneMapped={false} /></mesh>
      <mesh position={[0, 2.1, 0]}><coneGeometry args={[0.9, 1.9, 24, 1, true]} /><meshBasicMaterial color="#22d3ee" transparent opacity={0.08} side={THREE.DoubleSide} depthWrite={false} /></mesh>
    </group>
  );
}

// --- Tablero de desafíos (El Acertijo) ----------------------------------------------------------
function ChallengeBoard({ active }: Props) {
  const mat = useRef<THREE.MeshBasicMaterial>(null);
  const tex = useMemo(() => canvasTex(512, 320, (c) => {
    c.fillStyle = "#07140c"; c.fillRect(0, 0, 512, 320);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) {
      c.fillStyle = "#0d3a1c"; c.fillRect(14 + i * 124, 14 + j * 100, 112, 90);
      c.strokeStyle = "#4ade80"; c.lineWidth = 3; c.strokeRect(14 + i * 124, 14 + j * 100, 112, 90);
      c.fillStyle = "#6bff9b"; c.font = "bold 66px Impact, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText("?", 70 + i * 124, 60 + j * 100);
    }
  }), []);
  useEffect(() => () => tex.dispose(), [tex]);
  useFrame((s) => { mat.current?.color.setScalar(active ? 1.15 + Math.sin(s.clock.elapsedTime * 5) * 0.35 : 0.5); });
  return (
    <group position={[0, 0, -3]}>
      {[-1.9, 1.9].map((x) => <mesh key={x} position={[x, 1.3, -0.1]} castShadow material={plastic("#303944")}><boxGeometry args={[0.18, 2.6, 0.18]} /></mesh>)}
      <group position={[0, 1.9, 0]} rotation={[-0.06, 0, 0]}>
        <mesh castShadow material={plastic("#0b0f13")}><boxGeometry args={[4.5, 2.8, 0.16]} /></mesh>
        <mesh position={[0, 0, 0.09]}><planeGeometry args={[4.3, 2.6]} /><meshBasicMaterial ref={mat} map={tex} toneMapped={false} /></mesh>
      </group>
      {[-1.6, -0.5, 0.5, 1.6].map((x) => <mesh key={x} position={[x, 3.45, 0.05]}><boxGeometry args={[0.5, 0.1, 0.1]} /><meshBasicMaterial color={glow("#4ade80", active ? 3 : 0.8)} toneMapped={false} /></mesh>)}
    </group>
  );
}

// --- Muro de casos (El Joker) -------------------------------------------------------------------
function CaseWall({ active }: Props) {
  const notes = useMemo(() => Array.from({ length: 11 }, (_, i) => ({
    x: -1.8 + rnd(i * 3) * 3.6, y: -1 + rnd(i * 3 + 1) * 2, rot: (rnd(i * 3 + 2) - 0.5) * 0.5, c: ["#f2f3f2", "#f2cd37", "#e6a3b4", "#9fe3f2"][i % 4],
  })), []);
  const links: [number, number][] = [[0, 3], [3, 6], [6, 9], [1, 4], [4, 7], [7, 10], [2, 5], [5, 8], [0, 5], [3, 8]];
  const lineRef = useRef<{ material: THREE.LineBasicMaterial }[]>([]);
  void lineRef;
  return (
    <group position={[0, 0, -3]}>
      <mesh position={[0, 1.9, 0]} castShadow material={plastic("#3a2a1c")}><boxGeometry args={[4.8, 2.9, 0.14]} /></mesh>
      {notes.map((n, i) => (
        <group key={i} position={[n.x, 1.9 + n.y, 0.1]} rotation={[0, 0, n.rot]}>
          <mesh><planeGeometry args={[0.62, 0.48]} /><meshStandardMaterial color={n.c} roughness={0.9} /></mesh>
          <mesh position={[0, 0.2, 0.02]}><sphereGeometry args={[0.05, 8, 6]} /><meshBasicMaterial color="#e11d2e" /></mesh>
        </group>
      ))}
      {links.map(([a, b], i) => (
        <Line key={i} points={[[notes[a].x, 1.9 + notes[a].y + 0.2, 0.14], [notes[b].x, 1.9 + notes[b].y + 0.2, 0.14]]} color={active ? "#ff5a6a" : "#9b1c28"} lineWidth={active ? 3 : 1.6} />
      ))}
      <mesh position={[0, 3.6, 0.05]}><boxGeometry args={[4.6, 0.08, 0.08]} /><meshBasicMaterial color={glow("#c026d3", active ? 3 : 0.7)} toneMapped={false} /></mesh>
    </group>
  );
}

// --- Garaje del Batmóvil (Harley Quinn) --------------------------------------------------------
function Batmobile() {
  return (
    <group>
      <Brick w={8} d={3} h={1} color={P.black} pos={[0, 0.25, 0]} />
      <Brick w={4} d={2} h={1} color={P.darkGrey} pos={[-0.4, 0.25 + 0.528, 0]} />
      <mesh position={[-0.4, 0.25 + 1.056 + 0.04, 0]} material={plastic("#0b3a52")}><boxGeometry args={[1.5, 0.12, 0.7]} /></mesh>
      <Brick w={2} d={3} h={1} color={P.black} pos={[1.5, 0.25 + 0.528, 0]} />
      {[-1, 1].map((sg) => <mesh key={sg} position={[-1.9, 0.25 + 0.85, sg * 0.5]} rotation={[0, 0, -0.5]} castShadow material={plastic(P.black)}><boxGeometry args={[1.0, 0.07, 0.26]} /></mesh>)}
      {[[-1.2, 1], [-1.2, -1], [1.2, 1], [1.2, -1]].map(([x, z], i) => (
        <group key={i} position={[x, 0.3, z * 0.75]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh castShadow material={plastic(P.black)}><cylinderGeometry args={[0.3, 0.3, 0.26, 24]} /></mesh>
          <mesh position={[0, z * 0.14, 0]} material={plastic(P.grey)}><cylinderGeometry args={[0.15, 0.15, 0.03, 16]} /></mesh>
        </group>
      ))}
    </group>
  );
}

function VehicleBay({ active }: Props) {
  const spin = useRef<THREE.Group>(null);
  const lights = useRef<THREE.MeshBasicMaterial>(null);
  useFrame((_, dt) => {
    if (spin.current) spin.current.rotation.y += dt * (active ? 0.9 : 0.18);
    lights.current?.color.copy(glow("#ffe9a8", active ? 3.2 : 0.6));
  });
  return (
    <group position={[0, 0, -3.9]}>
      <mesh position={[0, 0.1, 0]} receiveShadow material={plastic("#1b2127")}><cylinderGeometry args={[2.7, 2.7, 0.2, 48]} /></mesh>
      <mesh position={[0, 0.21, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[2.35, 2.5, 48]} /><meshBasicMaterial color={glow("#ef4444", active ? 2.6 : 1.1)} toneMapped={false} /></mesh>
      <group ref={spin} position={[0, 0.2, 0]} scale={0.78}>
        <Batmobile />
        {[-0.28, 0.28].map((z) => <mesh key={z} position={[2.05, 0.4, z]}><boxGeometry args={[0.08, 0.1, 0.22]} /><meshBasicMaterial ref={z < 0 ? lights : undefined} color="#ffe9a8" toneMapped={false} /></mesh>)}
      </group>
    </group>
  );
}

// --- Zona de entrenamiento (Bane) --------------------------------------------------------------
function TrainingArea({ active }: Props) {
  const bag = useRef<THREE.Group>(null);
  const tex = useMemo(() => canvasTex(256, 256, (c) => {
    c.fillStyle = "#0f2a52"; c.fillRect(0, 0, 256, 256);
    c.strokeStyle = "#f2f3f2"; c.lineWidth = 8; c.strokeRect(10, 10, 236, 236);
    c.lineWidth = 4; c.beginPath(); c.arc(128, 128, 54, 0, Math.PI * 2); c.stroke();
  }), []);
  useEffect(() => () => tex.dispose(), [tex]);
  useFrame((s) => { if (bag.current) bag.current.rotation.x = Math.sin(s.clock.elapsedTime * (active ? 4.2 : 1.1)) * (active ? 0.55 : 0.05); });
  return (
    <group>
      <mesh position={[0, 0.07, 0]} receiveShadow><boxGeometry args={[5.4, 0.14, 5.4]} /><meshStandardMaterial map={tex} roughness={0.8} /></mesh>
      <group position={[0, 0, -3.3]}>
        {[-1.2, 1.2].map((x) => <mesh key={x} position={[x, 1.6, 0]} castShadow material={plastic("#4b545e")}><boxGeometry args={[0.2, 3.2, 0.2]} /></mesh>)}
        <mesh position={[0, 3.2, 0]} castShadow material={plastic("#4b545e")}><boxGeometry args={[2.6, 0.2, 0.2]} /></mesh>
        <group ref={bag} position={[0, 3.1, 0]}>
          <mesh position={[0, -0.45, 0]} material={plastic("#8a8f98")}><cylinderGeometry args={[0.03, 0.03, 0.9, 6]} /></mesh>
          <mesh position={[0, -1.75, 0]} castShadow material={plastic("#b91c1c")}><cylinderGeometry args={[0.5, 0.5, 1.7, 20]} /></mesh>
          <mesh position={[0, -1.4, 0]} material={plastic("#111")}><cylinderGeometry args={[0.52, 0.52, 0.2, 20]} /></mesh>
        </group>
      </group>
    </group>
  );
}

// --- Bóveda de trajes (Catwoman) ---------------------------------------------------------------
function SuitVault({ active }: Props) {
  const cases = useRef<THREE.Group[]>([]);
  useFrame((_, dt) => { cases.current.forEach((g, i) => { if (g) g.rotation.y += dt * (active ? 1.4 : 0.25) * (i % 2 ? -1 : 1); }); });
  return (
    <group position={[0, 0, -3]}>
      {[-2.4, 0, 2.4].map((x, i) => (
        <group key={x} position={[x, 0, 0]}>
          <mesh position={[0, 0.15, 0]} castShadow material={plastic("#1b2127")}><boxGeometry args={[1.5, 0.3, 1.2]} /></mesh>
          <mesh position={[0, 1.6, 0]}><boxGeometry args={[1.5, 2.6, 1.2]} /><meshPhysicalMaterial color="#bfeaf5" transparent opacity={0.14} roughness={0.05} depthWrite={false} /></mesh>
          <mesh position={[0, 2.95, 0]}><boxGeometry args={[1.5, 0.08, 1.2]} /><meshBasicMaterial color={glow("#dff6fb", active ? 2.6 : 1.1)} toneMapped={false} /></mesh>
          <group ref={(g) => { if (g) cases.current[i] = g; }} position={[0, 0, 0]}>
            <mesh position={[0, 1.25, 0]} castShadow material={plastic(["#2c3138", "#0f2a52", "#05131D"][i])}><boxGeometry args={[0.7, 0.9, 0.38]} /></mesh>
            <mesh position={[0, 1.95, 0]} castShadow material={plastic(["#2c3138", "#0f2a52", "#05131D"][i])}><sphereGeometry args={[0.27, 14, 12]} /></mesh>
            {[-0.14, 0.14].map((ex) => <mesh key={ex} position={[ex, 2.25, 0]} castShadow material={plastic(["#2c3138", "#0f2a52", "#05131D"][i])}><coneGeometry args={[0.09, 0.28, 4]} /></mesh>)}
            <mesh position={[0, 1.3, 0.2]}><circleGeometry args={[0.16, 18]} /><meshBasicMaterial color="#f2cd37" /></mesh>
          </group>
        </group>
      ))}
    </group>
  );
}

// --- Tienda Bat-Mite (El Pingüino): máquina recreativa con ecualizador -----------------------------
function BatMiteShop({ active }: Props) {
  const bars = useRef<THREE.Mesh[]>([]);
  const spk = useRef<THREE.Mesh[]>([]);
  useFrame((s) => {
    const t = s.clock.elapsedTime;
    bars.current.forEach((m, i) => { if (m) { const a = active ? 0.35 + 0.65 * Math.abs(Math.sin(t * 5 + i * 0.9)) : 0.12 + 0.05 * Math.sin(t * 1.5 + i); m.scale.y = a; m.position.y = 1.55 + a * 0.5; } });
    spk.current.forEach((m) => { if (m) m.scale.setScalar(1 + (active ? Math.abs(Math.sin(t * 8)) * 0.12 : 0)); });
  });
  return (
    <group position={[0, 0, -2.7]}>
      <mesh position={[0, 1.6, 0]} castShadow material={plastic("#1a1030")}><boxGeometry args={[2.7, 3.2, 0.95]} /></mesh>
      {[[-1.36, 0], [1.36, 0]].map(([x]) => <mesh key={x} position={[x, 1.6, 0.48]}><boxGeometry args={[0.07, 3.2, 0.07]} /><meshBasicMaterial color={glow("#e879f9", active ? 3 : 1.3)} toneMapped={false} /></mesh>)}
      {[0.02, 3.18].map((y) => <mesh key={y} position={[0, y, 0.48]}><boxGeometry args={[2.7, 0.07, 0.07]} /><meshBasicMaterial color={glow("#22d3ee", active ? 3 : 1.3)} toneMapped={false} /></mesh>)}
      <mesh position={[0, 1.9, 0.49]}><planeGeometry args={[2.1, 1.4]} /><meshBasicMaterial color="#05060f" /></mesh>
      {Array.from({ length: 9 }, (_, i) => (
        <mesh key={i} ref={(m) => { if (m) bars.current[i] = m; }} position={[-0.9 + i * 0.225, 1.55, 0.5]}>
          <boxGeometry args={[0.15, 1, 0.03]} /><meshBasicMaterial color={glow(i % 2 ? "#22d3ee" : "#e879f9", 2)} toneMapped={false} />
        </mesh>
      ))}
      {[-1.9, 1.9].map((x) => <mesh key={x} ref={(m) => { if (m) spk.current.push(m); }} position={[x, 0.7, 0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow material={plastic("#111")}><cylinderGeometry args={[0.55, 0.55, 0.5, 24]} /></mesh>)}
    </group>
  );
}

// --- Mesa de trabajo (Nightwing): banco con brazo robótico y chispas ---------------------------------
function Workbench({ active }: Props) {
  const a1 = useRef<THREE.Group>(null);
  const a2 = useRef<THREE.Group>(null);
  const tex = useMemo(() => screenTexture(5, "#4ade80", "MONTAJE"), []);
  useEffect(() => () => tex.dispose(), [tex]);
  useFrame((s) => {
    const t = s.clock.elapsedTime;
    if (a1.current) a1.current.rotation.z = -0.6 + Math.sin(t * (active ? 2.6 : 0.7)) * (active ? 0.5 : 0.1);
    if (a2.current) a2.current.rotation.z = 1.1 + Math.sin(t * (active ? 3.4 : 0.9) + 1) * (active ? 0.6 : 0.1);
  });
  return (
    <group position={[0, 0, -2.6]}>
      <mesh position={[0, 0.95, 0]} castShadow receiveShadow material={plastic("#4b545e")}><boxGeometry args={[4.4, 0.18, 1.5]} /></mesh>
      {[[-2, 0.5], [2, 0.5], [-2, -0.5], [2, -0.5]].map(([x, z], i) => <mesh key={i} position={[x, 0.47, z * 1.2]} material={plastic("#232b33")}><boxGeometry args={[0.16, 0.95, 0.16]} /></mesh>)}
      <mesh position={[0, 2.35, -0.72]} castShadow material={plastic("#2c353e")}><boxGeometry args={[4.4, 2.2, 0.1]} /></mesh>
      {Array.from({ length: 9 }, (_, i) => <mesh key={i} position={[-1.8 + (i % 5) * 0.9, 1.8 + Math.floor(i / 5) * 0.8, -0.62]} material={plastic(["#f2cd37", "#c91a09", "#0055BF", "#a0a5a9", "#237841"][i % 5])}><boxGeometry args={[0.5, 0.18, 0.08]} /></mesh>)}
      <mesh position={[-1.35, 1.7, -0.2]} rotation={[-0.2, 0.2, 0]}><planeGeometry args={[1.5, 0.95]} /><meshBasicMaterial map={tex} toneMapped={false} color={active ? "#ffffff" : "#4d6b57"} /></mesh>
      <group position={[1.1, 1.04, 0]}>
        <mesh castShadow material={plastic("#f2cd37")}><cylinderGeometry args={[0.3, 0.34, 0.3, 20]} /></mesh>
        <group ref={a1} position={[0, 0.2, 0]}>
          <mesh position={[0, 0.5, 0]} castShadow material={plastic("#a0a5a9")}><boxGeometry args={[0.2, 1, 0.2]} /></mesh>
          <group ref={a2} position={[0, 1, 0]}>
            <mesh position={[0, 0.45, 0]} castShadow material={plastic("#f2cd37")}><boxGeometry args={[0.18, 0.9, 0.18]} /></mesh>
            <mesh position={[0, 0.95, 0]}><sphereGeometry args={[0.1, 10, 8]} /><meshBasicMaterial color={glow("#ffb347", active ? 4 : 0.5)} toneMapped={false} /></mesh>
          </group>
        </group>
      </group>
      {active && <Sparkles count={22} scale={[1.8, 1.4, 1.2]} position={[1.1, 2.6, 0.2]} size={4} speed={2.4} color="#ffb347" />}
    </group>
  );
}

// --- Mesa de pruebas (Dos Caras): escáner y moneda -----------------------------------------------------
function EvidenceTable({ active, color }: Props) {
  const coin = useRef<THREE.Mesh>(null);
  const beam = useRef<THREE.Mesh>(null);
  useFrame((s, dt) => {
    if (coin.current) coin.current.rotation.x += dt * (active ? 7 : 0.9);
    if (beam.current) beam.current.position.x = Math.sin(s.clock.elapsedTime * (active ? 2.4 : 0.6)) * 1.35;
  });
  return (
    <group position={[0, 0, -2.6]}>
      <mesh position={[0, 0.95, 0]} castShadow receiveShadow material={plastic("#232b33")}><boxGeometry args={[3.8, 0.14, 1.7]} /></mesh>
      <mesh position={[0, 0.99, 0]}><boxGeometry args={[3.6, 0.04, 1.5]} /><meshPhysicalMaterial color="#9fe3f2" transparent opacity={0.2} roughness={0.05} /></mesh>
      {[[-1.7, 0.7], [1.7, 0.7], [-1.7, -0.7], [1.7, -0.7]].map(([x, z], i) => <mesh key={i} position={[x, 0.47, z]} material={plastic("#232b33")}><boxGeometry args={[0.14, 0.95, 0.14]} /></mesh>)}
      <mesh position={[0, 1.95, 0]} castShadow material={plastic("#4b545e")}><torusGeometry args={[1.0, 0.07, 8, 32, Math.PI]} /></mesh>
      <mesh ref={beam} position={[0, 1.5, 0]}><boxGeometry args={[0.04, 1.0, 1.5]} /><meshBasicMaterial color={glow("#4ade80", active ? 3 : 1)} transparent opacity={0.5} toneMapped={false} /></mesh>
      {[-0.9, -0.2].map((x, i) => <mesh key={x} position={[x, 1.03, 0.2]} rotation={[-Math.PI / 2, 0, 0.2 * (i ? -1 : 1)]}><planeGeometry args={[0.7, 0.9]} /><meshStandardMaterial color="#f2f3f2" roughness={0.9} /></mesh>)}
      <mesh position={[1.3, 1.1, 0]} castShadow material={plastic("#1b2127")}><cylinderGeometry args={[0.35, 0.4, 0.3, 20]} /></mesh>
      <mesh ref={coin} position={[1.3, 1.65, 0]} rotation={[0, 0, Math.PI / 2]} castShadow><cylinderGeometry args={[0.45, 0.45, 0.08, 36]} /><meshStandardMaterial color="#d7dbe0" metalness={0.85} roughness={0.28} /></mesh>
      <mesh position={[-1.5, 1.2, -0.5]}><sphereGeometry args={[0.1, 10, 8]} /><meshBasicMaterial color={glow(color, 3)} toneMapped={false} /></mesh>
    </group>
  );
}

const STATION: Record<string, (p: Props) => React.ReactElement> = {
  chief: Batcomputer, director: ChallengeBoard, scriptwriter: CaseWall, publisher: VehicleBay, voice: TrainingArea,
  resources: SuitVault, sound: BatMiteShop, editor: Workbench, reviewer: EvidenceTable,
};

/** Las nueve instalaciones, colocadas en el hub y orientadas hacia Batman. */
export function Facilities({ agents, colors }: { agents: Record<string, AgentState>; colors: Record<string, string> }) {
  return (
    <>
      {Object.entries(HUB).map(([name]) => {
        const Station = STATION[name];
        const s = HUB[name];
        return (
          <group key={name} position={[s.x, FLOOR_Y, s.z]} rotation={[0, facingYaw(name), 0]} scale={HUB_SCALE}>
            <Station active={agents[name]?.status === "running"} color={colors[name] ?? "#ffffff"} />
            {/* foco propio: ilumina la instalación y se intensifica mientras el agente trabaja */}
            <pointLight position={[0, 3.4, 0.4]} color={agents[name]?.status === "running" ? colors[name] ?? "#ffffff" : "#bfe3f0"} intensity={agents[name]?.status === "running" ? 38 : 16} distance={10} />
          </group>
        );
      })}
    </>
  );
}

/** Placas de tacos bajo cada instalación y la tarima central de Batman. */
export function FloorPads() {
  const { pads, studs } = useMemo(() => {
    const pads: { x: number; z: number; r: number }[] = [];
    const studs: { x: number; y: number; z: number; color: string }[] = [];
    for (const name of Object.keys(HUB)) {
      const r = (name === "chief" ? 3.6 : 3.4) * HUB_SCALE;
      const [cx, cz] = localToWorld(name, 0, -1.3 * HUB_SCALE);
      const c = name === "chief" ? { x: HUB.chief.x, z: HUB.chief.z + 0 } : { x: cx, z: cz };
      pads.push({ ...c, r });
      for (const [sx, sz] of ellipseStuds(r, r)) studs.push({ x: c.x + sx, y: FLOOR_Y, z: c.z + sz, color: rnd(sx * 9 + sz * 5) > 0.88 ? "#434951" : "#51575f" });
    }
    return { pads, studs };
  }, []);
  return (
    <>
      {pads.map((p, i) => (
        <group key={i} position={[p.x, FLOOR_Y - 0.15, p.z]}>
          <mesh receiveShadow castShadow material={plastic("#2e3339")}><cylinderGeometry args={[p.r, p.r, 0.3, 56]} /></mesh>
        </group>
      ))}
      <StudInstances items={studs} />
    </>
  );
}

/** Murciélagos que vuelan por la cueva (instanciados; el aleteo es una oscilación de escala). */
export function BatSwarm({ count = 16 }: { count?: number }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const geo = useMemo(() => batGeometry(0.014, 0.03), []);
  const tmp = useMemo(() => new THREE.Object3D(), []);
  useLayoutEffect(() => () => geo.dispose(), [geo]);
  useFrame((s) => {
    const m = ref.current;
    if (!m) return;
    const t = s.clock.elapsedTime;
    for (let i = 0; i < count; i++) {
      const a = t * (0.12 + (i % 5) * 0.03) + i * 1.7, r = 9 + (i % 6) * 2.2;
      tmp.position.set(Math.cos(a) * r, FLOOR_Y + 11 + Math.sin(t * 0.7 + i) * 1.4 + (i % 4) * 0.8, Math.sin(a) * r * 0.8 - 4);
      tmp.rotation.set(0, -a + Math.PI / 2, 0);
      tmp.scale.set(1, 0.35 + 0.65 * Math.abs(Math.sin(t * 9 + i)), 1);
      tmp.updateMatrix();
      m.setMatrixAt(i, tmp.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  });
  return (
    <instancedMesh ref={ref} args={[geo, undefined, count]} frustumCulled={false}>
      <meshBasicMaterial color="#05080b" side={THREE.DoubleSide} />
    </instancedMesh>
  );
}
