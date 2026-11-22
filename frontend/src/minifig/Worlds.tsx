/**
 * Escenarios inmersivos de los perfiles GTA VI (Vice City al atardecer), YouTube Kids (sala de juegos) y
 * Deportes (estadio de noche). Todo procedural: sin descargas, funciona sin Internet.
 */
import { Sparkles, Stars } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { AgentState } from "../types";
import { FLOOR_Y, NamePlate, canvasTex } from "./Batcave";
import { rnd } from "./bricks";
import { HUB, HUB_SCALE, facingYaw } from "./hub";

function gradientSky(stops: [number, string][]): THREE.CanvasTexture {
  return canvasTex(16, 512, (c) => {
    const g = c.createLinearGradient(0, 0, 0, 512);
    for (const [p, col] of stops) g.addColorStop(p, col);
    c.fillStyle = g;
    c.fillRect(0, 0, 16, 512);
  });
}

function SkyDome({ tex, radius = 150 }: { tex: THREE.Texture; radius?: number }) {
  return (
    <mesh>
      <sphereGeometry args={[radius, 32, 24]} />
      <meshBasicMaterial map={tex} side={THREE.BackSide} fog={false} toneMapped={false} />
    </mesh>
  );
}

/** Texto luminoso (cartel de neón) dibujado en una textura. */
function neonTexture(text: string, color: string, font = "italic 900 150px 'Lilita One', Impact, sans-serif", w = 1024, h = 256): THREE.CanvasTexture {
  return canvasTex(w, h, (c) => {
    c.font = font;
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.shadowColor = color;
    for (const blur of [40, 20, 8]) { c.shadowBlur = blur; c.fillStyle = color; c.fillText(text, w / 2, h / 2); }
    c.shadowBlur = 0;
    c.fillStyle = "#ffffff";
    c.globalAlpha = 0.85;
    c.fillText(text, w / 2, h / 2);
  });
}

function Billboard({ tex, position, size, rotation = [0, 0, 0] }: { tex: THREE.Texture; position: [number, number, number]; size: [number, number]; rotation?: [number, number, number] }) {
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={size} />
      <meshBasicMaterial map={tex} transparent toneMapped={false} depthWrite={false} />
    </mesh>
  );
}

function useBob(speed = 1, amp = 0.3, seed = 0) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (ref.current) ref.current.position.y = Math.sin(clock.elapsedTime * speed + seed) * amp; });
  return ref;
}

/* =================================================================================== GTA VI */

function PalmTree({ position, height = 9, seed = 0 }: { position: [number, number, number]; height?: number; seed?: number }) {
  const sway = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (sway.current) sway.current.rotation.z = Math.sin(clock.elapsedTime * 0.7 + seed) * 0.04; });
  const segs = 9;
  const bend = 0.9 + rnd(seed) * 1.2;
  return (
    <group position={position} rotation={[0, rnd(seed * 3) * Math.PI * 2, 0]}>
      <group ref={sway}>
        {[...Array(segs)].map((_, i) => {
          const t = i / segs;
          return (
            <mesh key={i} position={[bend * t * t * 2, t * height, 0]} rotation={[0, 0, -bend * t * 0.35]} castShadow>
              <cylinderGeometry args={[0.24 - t * 0.08, 0.3 - t * 0.08, height / segs + 0.05, 8]} />
              <meshStandardMaterial color={i % 2 ? "#7a5233" : "#8d6340"} roughness={0.9} />
            </mesh>
          );
        })}
        <group position={[bend * 2, height, 0]}>
          {[...Array(8)].map((_, i) => (
            <mesh key={i} rotation={[0.55 + rnd(seed + i) * 0.3, (i / 8) * Math.PI * 2, 0]} position={[0, 0, 0]}>
              <coneGeometry args={[0.55, 4.2, 4, 1]} />
              <meshStandardMaterial color={i % 2 ? "#1f7a3a" : "#2b9a4b"} roughness={0.7} side={THREE.DoubleSide} />
            </mesh>
          ))}
          {[0, 1, 2].map((i) => <mesh key={i} position={[Math.cos(i * 2.1) * 0.25, -0.25, Math.sin(i * 2.1) * 0.25]}><sphereGeometry args={[0.2, 10, 10]} /><meshStandardMaterial color="#5a3d1e" /></mesh>)}
        </group>
      </group>
    </group>
  );
}

function Skyline({ z, tint }: { z: number; tint: string }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const windows = useMemo(() => canvasTex(64, 128, (c) => {
    c.fillStyle = "#120a22"; c.fillRect(0, 0, 64, 128);
    for (let y = 4; y < 128; y += 8) for (let x = 4; x < 64; x += 8) {
      const r = rnd(x * 7 + y * 13);
      c.fillStyle = r > 0.55 ? (r > 0.85 ? "#ffd27a" : "#ff8fd0") : "#1c1233";
      c.fillRect(x, y, 4, 5);
    }
  }), []);
  const count = 46;
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const o = new THREE.Object3D();
    for (let i = 0; i < count; i++) {
      const w = 4 + rnd(i * 3) * 6, h = 5 + rnd(i * 5) * (Math.abs(i - count / 2) < 6 ? 8 : 20), d = 4 + rnd(i * 7) * 4;
      o.position.set(-115 + i * 5 + rnd(i) * 2, FLOOR_Y + h / 2, z - rnd(i * 11) * 14);
      o.scale.set(w, h, d);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
  }, [z]);
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={tint} emissive="#ffffff" emissiveMap={windows} emissiveIntensity={0.9} map={windows} />
    </instancedMesh>
  );
}

function SynthSun() {
  const tex = useMemo(() => canvasTex(512, 512, (c) => {
    const g = c.createLinearGradient(0, 0, 0, 512);
    g.addColorStop(0, "#fff3a0"); g.addColorStop(0.5, "#ff9f43"); g.addColorStop(1, "#ff2f8e");
    c.fillStyle = g; c.beginPath(); c.arc(256, 256, 250, 0, 7); c.fill();
    c.globalCompositeOperation = "destination-out";
    for (let i = 0; i < 9; i++) { const y = 300 + i * 24; c.fillRect(0, y, 512, 4 + i * 1.6); }
  }), []);
  return <Billboard tex={tex} position={[0, 8, -124]} size={[52, 52]} />;
}

function Ocean() {
  const tex = useMemo(() => {
    const t = canvasTex(256, 256, (c) => {
      c.fillStyle = "#1b2f6b"; c.fillRect(0, 0, 256, 256);
      c.strokeStyle = "rgba(255,120,200,0.45)"; c.lineWidth = 2;
      for (let y = 0; y < 256; y += 16) { c.beginPath(); for (let x = 0; x <= 256; x += 8) c.lineTo(x, y + Math.sin(x / 20 + y) * 3); c.stroke(); }
    });
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(20, 8);
    return t;
  }, []);
  useFrame((_, dt) => { tex.offset.x += dt * 0.01; });
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y - 0.4, -80]}>
      <planeGeometry args={[320, 110]} />
      <meshStandardMaterial map={tex} metalness={0.4} roughness={0.25} emissive="#2a1050" emissiveIntensity={0.4} />
    </mesh>
  );
}

function decoFloor(): THREE.CanvasTexture {
  const t = canvasTex(1024, 1024, (c) => {
    c.fillStyle = "#f3e3d3"; c.fillRect(0, 0, 1024, 1024);
    const cx = 512;
    const rings = ["#ff4fa3", "#f3e3d3", "#26c6da", "#f3e3d3", "#ff9f43", "#f3e3d3"];
    for (let i = 0; i < rings.length; i++) { c.fillStyle = rings[i]; c.beginPath(); c.arc(cx, cx, 500 - i * 22, 0, 7); c.fill(); }
    for (let i = 0; i < 24; i++) {
      c.fillStyle = i % 2 ? "#e9cdb8" : "#f7eadf";
      c.beginPath(); c.moveTo(cx, cx); c.arc(cx, cx, 368, (i / 24) * Math.PI * 2, ((i + 1) / 24) * Math.PI * 2); c.fill();
    }
    c.fillStyle = "#26c6da"; c.beginPath(); c.arc(cx, cx, 96, 0, 7); c.fill();
    c.fillStyle = "#ff4fa3"; c.beginPath(); c.arc(cx, cx, 70, 0, 7); c.fill();
  });
  return t;
}

export function ViceCity({ active }: { active: boolean }) {
  const sky = useMemo(() => gradientSky([[0, "#120726"], [0.32, "#4b1670"], [0.46, "#ff4fa3"], [0.5, "#ffb15c"], [0.52, "#2a1350"], [1, "#0d0716"]]), []);
  const floor = useMemo(decoFloor, []);
  const sign = useMemo(() => neonTexture("VICE CITY", "#ff4fa3"), []);
  const sign2 = useMemo(() => neonTexture("LEONIDA", "#5ee7ff", "900 120px 'Lilita One', Impact, sans-serif"), []);
  const palms = useMemo(() => {
    const out: [number, number, number][] = [];
    for (let i = 0; i < 16; i++) {
      const a = -Math.PI * 0.95 + (i / 15) * Math.PI * 1.25; // detrás y a los lados (no delante de la cámara)
      const r = 25 + rnd(i * 9) * 5;
      out.push([Math.sin(a) * r, FLOOR_Y, -Math.cos(a) * r]);
    }
    return out;
  }, []);
  return (
    <>
      <fog attach="fog" args={["#3a1550", 60, 190]} />
      <SkyDome tex={sky} />
      <SynthSun />
      <Ocean />
      <Skyline z={-100} tint="#2c1748" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y, 0]} receiveShadow>
        <circleGeometry args={[30, 96]} />
        <meshStandardMaterial map={floor} roughness={0.35} metalness={0.05} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y - 0.02, 0]}>
        <ringGeometry args={[30, 70, 64]} />
        <meshStandardMaterial color="#d8c3a5" roughness={0.9} />
      </mesh>
      {[29.6, 18.5].map((r, i) => (
        <mesh key={r} rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y + 0.02, 0]}>
          <ringGeometry args={[r - 0.12, r, 96]} />
          <meshBasicMaterial color={i ? "#5ee7ff" : "#ff4fa3"} toneMapped={false} />
        </mesh>
      ))}
      {palms.map((p, i) => <PalmTree key={i} position={p} seed={i + 1} height={8 + rnd(i * 4) * 4} />)}
      <Billboard tex={sign} position={[0, 9.5, -27]} size={[22, 5.5]} />
      <Billboard tex={sign2} position={[0, 6.6, -27.2]} size={[12, 3]} />
      <pointLight position={[0, 9, -24]} color="#ff4fa3" intensity={active ? 160 : 90} distance={40} />
      <pointLight position={[-20, 6, 8]} color="#5ee7ff" intensity={70} distance={40} />
      <pointLight position={[20, 6, 8]} color="#ff9f43" intensity={70} distance={40} />
      <directionalLight position={[-10, 8, -30]} intensity={1.6} color="#ffb07a" />
      <Sparkles count={60} scale={[50, 10, 40]} position={[0, 4, -5]} size={3} speed={0.3} color="#ffd6f0" />
    </>
  );
}

/* =================================================================================== YouTube Kids */

function Cloud({ position, seed }: { position: [number, number, number]; seed: number }) {
  const ref = useBob(0.4, 0.6, seed);
  return (
    <group position={position}>
      <group ref={ref}>
        {[[0, 0, 0, 2.2], [1.9, -0.3, 0.2, 1.6], [-1.9, -0.4, 0, 1.5], [0.9, 0.9, -0.2, 1.4], [-0.8, 0.8, 0.1, 1.3]].map(([x, y, z, r], i) => (
          <mesh key={i} position={[x, y, z]}><sphereGeometry args={[r, 20, 16]} /><meshStandardMaterial color="#ffffff" roughness={0.9} /></mesh>
        ))}
      </group>
    </group>
  );
}

function Rainbow() {
  const colors = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be", "#007aff", "#af52de"];
  return (
    <group position={[0, FLOOR_Y - 2, -46]}>
      {colors.map((c, i) => (
        <mesh key={c}><torusGeometry args={[34 - i * 1.6, 0.8, 12, 80, Math.PI]} /><meshStandardMaterial color={c} emissive={c} emissiveIntensity={0.25} roughness={0.6} /></mesh>
      ))}
    </group>
  );
}

function letterTex(ch: string, bg: string): THREE.CanvasTexture {
  return canvasTex(128, 128, (c) => {
    c.fillStyle = bg; c.fillRect(0, 0, 128, 128);
    c.strokeStyle = "rgba(255,255,255,0.7)"; c.lineWidth = 8; c.strokeRect(8, 8, 112, 112);
    c.font = "900 84px 'Lilita One', sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillStyle = "#ffffff"; c.fillText(ch, 64, 70);
  });
}

function ToyBlock({ position, ch, color, rot = 0 }: { position: [number, number, number]; ch: string; color: string; rot?: number }) {
  const tex = useMemo(() => letterTex(ch, color), [ch, color]);
  return (
    <mesh position={position} rotation={[0, rot, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.8, 1.8, 1.8]} />
      <meshStandardMaterial map={tex} roughness={0.5} />
    </mesh>
  );
}

function Balloon({ position, color, seed }: { position: [number, number, number]; color: string; seed: number }) {
  const ref = useBob(0.8, 0.5, seed);
  return (
    <group position={position}>
      <group ref={ref}>
        <mesh position={[0, 4, 0]} scale={[1, 1.15, 1]}><sphereGeometry args={[0.8, 24, 20]} /><meshStandardMaterial color={color} roughness={0.2} metalness={0.05} /></mesh>
        <mesh position={[0, 1.6, 0]}><cylinderGeometry args={[0.015, 0.015, 4.2, 4]} /><meshStandardMaterial color="#ffffff" /></mesh>
      </group>
    </group>
  );
}

function playMat(): THREE.CanvasTexture {
  return canvasTex(1024, 1024, (c) => {
    const cols = ["#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#c77dff", "#ff9f1c"];
    const n = 10, s = 1024 / n;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      c.fillStyle = cols[(x + y * 3) % cols.length];
      c.fillRect(x * s, y * s, s, s);
      c.fillStyle = "rgba(255,255,255,0.25)";
      c.beginPath(); c.arc(x * s + s / 2, y * s, s * 0.16, 0, 7); c.fill();
    }
  });
}

export function Playroom({ active }: { active: boolean }) {
  const sky = useMemo(() => gradientSky([[0, "#4aa8ff"], [0.45, "#a6dcff"], [0.55, "#e9f7ff"], [1, "#e9f7ff"]]), []);
  const mat = useMemo(playMat, []);
  const sign = useMemo(() => canvasTex(1024, 300, (c) => {
    c.fillStyle = "#ff0033";
    const r = 60; c.beginPath(); c.roundRect(40, 40, 300, 220, r); c.fill();
    c.fillStyle = "#fff"; c.beginPath(); c.moveTo(150, 95); c.lineTo(150, 205); c.lineTo(245, 150); c.closePath(); c.fill();
    c.font = "900 190px 'Lilita One', sans-serif"; c.textBaseline = "middle";
    const letters = "Kids"; const cols = ["#ff3b30", "#ffcc00", "#34c759", "#007aff"];
    let x = 380; for (let i = 0; i < letters.length; i++) { c.lineWidth = 16; c.strokeStyle = "#ffffff"; c.strokeText(letters[i], x, 160); c.fillStyle = cols[i]; c.fillText(letters[i], x, 160); x += c.measureText(letters[i]).width + 8; }
  }), []);
  const sun = useRef<THREE.Group>(null);
  useFrame((_, dt) => { if (sun.current) sun.current.rotation.z += dt * 0.2; });
  return (
    <>
      <fog attach="fog" args={["#dff3ff", 60, 180]} />
      <SkyDome tex={sky} />
      <group ref={sun} position={[26, 20, -60]}>
        <mesh><circleGeometry args={[5, 40]} /><meshBasicMaterial color="#ffd60a" toneMapped={false} fog={false} /></mesh>
        {[...Array(12)].map((_, i) => (
          <mesh key={i} rotation={[0, 0, (i / 12) * Math.PI * 2]} position={[Math.cos((i / 12) * Math.PI * 2) * 7, Math.sin((i / 12) * Math.PI * 2) * 7, -0.1]}>
            <planeGeometry args={[2.6, 0.8]} /><meshBasicMaterial color="#ffb703" toneMapped={false} fog={false} />
          </mesh>
        ))}
      </group>
      <Rainbow />
      {[[-30, 16, -50], [10, 22, -70], [38, 12, -40], [-50, 20, -30], [55, 18, -10]].map((p, i) => <Cloud key={i} position={p as [number, number, number]} seed={i * 1.3} />)}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y - 0.03, 0]} receiveShadow>
        <circleGeometry args={[120, 64]} />
        <meshStandardMaterial color="#7ed957" roughness={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y, 0]} receiveShadow>
        <circleGeometry args={[27, 80]} />
        <meshStandardMaterial map={mat} roughness={0.8} />
      </mesh>
      {[["A", "#ff3b30", -22, -16], ["B", "#007aff", -24.5, -13], ["C", "#34c759", -20, -19.5], ["Y", "#ff9500", 22, -16], ["T", "#af52de", 24, -13], ["!", "#ffcc00", 19.5, -19.5]].map(([ch, col, x, z], i) => (
        <ToyBlock key={i} ch={ch as string} color={col as string} position={[x as number, FLOOR_Y + 0.9, z as number]} rot={i * 0.4} />
      ))}
      <ToyBlock ch="★" color="#ff2d55" position={[-22, FLOOR_Y + 2.7, -16]} rot={0.2} />
      <ToyBlock ch="♪" color="#5856d6" position={[22, FLOOR_Y + 2.7, -16]} rot={-0.3} />
      {[["#ff3b30", -26, 2], ["#ffcc00", -28, 8], ["#34c759", 26, 2], ["#007aff", 28, 8], ["#ff2d55", -16, -24], ["#af52de", 16, -24]].map(([c, x, z], i) => (
        <Balloon key={i} color={c as string} position={[x as number, FLOOR_Y, z as number]} seed={i * 1.7} />
      ))}
      <Billboard tex={sign} position={[0, 10.5, -28]} size={[17, 5]} />
      <hemisphereLight args={["#bde3ff", "#7ed957", 1.4]} />
      <directionalLight position={[10, 18, 12]} intensity={2.2} color="#fff6e0" />
      {active && <Sparkles count={90} scale={[40, 12, 30]} position={[0, 5, 0]} size={6} speed={0.6} color="#ffd60a" />}
    </>
  );
}

/* =================================================================================== Deportes */

function pitchTexture(): THREE.CanvasTexture {
  return canvasTex(1536, 1024, (c) => {
    for (let i = 0; i < 16; i++) { c.fillStyle = i % 2 ? "#2e8b3e" : "#33994a"; c.fillRect(i * 96, 0, 96, 1024); }
    c.strokeStyle = "rgba(255,255,255,0.92)"; c.lineWidth = 8;
    c.strokeRect(40, 40, 1456, 944);
    c.beginPath(); c.moveTo(768, 40); c.lineTo(768, 984); c.stroke();
    c.beginPath(); c.arc(768, 512, 130, 0, 7); c.stroke();
    c.fillStyle = "#fff"; c.beginPath(); c.arc(768, 512, 9, 0, 7); c.fill();
    c.strokeRect(40, 262, 230, 500); c.strokeRect(1266, 262, 230, 500);
    c.strokeRect(40, 382, 80, 260); c.strokeRect(1416, 382, 80, 260);
  });
}

function Crowd({ side, active }: { side: 0 | 1 | 2 | 3; active: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const rows = 6, cols = 46, count = rows * cols;
  const base = useMemo(() => {
    const out: { x: number; y: number; z: number; ph: number }[] = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      out.push({ x: -34 + c * 1.5 + (r % 2) * 0.5, y: FLOOR_Y + 1.6 + r * 1.3, z: r * 1.4, ph: rnd(r * 100 + c) * 6 });
    }
    return out;
  }, []);
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    const palette = ["#e11d48", "#f8fafc", "#1d4ed8", "#facc15", "#16a34a", "#f97316"];
    const col = new THREE.Color();
    base.forEach((_, i) => { col.set(palette[Math.floor(rnd(i * 7 + side) * palette.length)]); m.setColorAt(i, col); });
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [base, side]);
  const o = useMemo(() => new THREE.Object3D(), []);
  useFrame(({ clock }) => {
    const m = ref.current;
    if (!m) return;
    const t = clock.elapsedTime;
    base.forEach((p, i) => {
      const jump = active ? Math.max(0, Math.sin(t * 6 + p.ph)) * 0.45 : Math.max(0, Math.sin(t * 1.2 + p.ph)) * 0.05;
      o.position.set(p.x, p.y + jump, p.z);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });
  const rot = [0, Math.PI, Math.PI / 2, -Math.PI / 2][side];
  const dist = side < 2 ? 31 : 40;
  return (
    <group rotation={[0, rot, 0]}>
      <group position={[0, 0, -dist]} rotation={[0, Math.PI, 0]}>
        {[...Array(rows)].map((_, r) => (
          <mesh key={r} position={[0, FLOOR_Y + 0.6 + r * 1.3, r * 1.4]} receiveShadow>
            <boxGeometry args={[72, 1.3, 1.4]} />
            <meshStandardMaterial color={r % 2 ? "#1f2937" : "#273244"} roughness={0.9} />
          </mesh>
        ))}
        <instancedMesh ref={ref} args={[undefined, undefined, count]}>
          <capsuleGeometry args={[0.3, 0.5, 4, 8]} />
          <meshStandardMaterial roughness={0.8} />
        </instancedMesh>
      </group>
    </group>
  );
}

function FloodLight({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 11, 0]}><cylinderGeometry args={[0.3, 0.5, 26, 10]} /><meshStandardMaterial color="#9ca3af" metalness={0.6} roughness={0.4} /></mesh>
      <group position={[0, 24.5, 0]} rotation={[0.5, Math.atan2(-position[0], -position[2]), 0]}>
        <mesh><boxGeometry args={[5, 3, 0.5]} /><meshStandardMaterial color="#374151" /></mesh>
        {[...Array(12)].map((_, i) => (
          <mesh key={i} position={[-1.9 + (i % 4) * 1.27, -0.9 + Math.floor(i / 4) * 0.9, 0.3]}>
            <circleGeometry args={[0.36, 16]} /><meshBasicMaterial color="#fffbe6" toneMapped={false} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

function scoreTexture(): THREE.CanvasTexture {
  return canvasTex(1024, 400, (c) => {
    c.fillStyle = "#05080d"; c.fillRect(0, 0, 1024, 400);
    c.strokeStyle = "#22c55e"; c.lineWidth = 10; c.strokeRect(8, 8, 1008, 384);
    c.font = "900 76px Impact, 'Arial Narrow', sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillStyle = "#facc15"; c.fillText("YTAUTO", 165, 140); c.fillStyle = "#fafafa"; c.fillText("RIVAL", 860, 140);
    c.font = "900 150px Impact, sans-serif"; c.fillStyle = "#ffffff"; c.fillText("3 - 0", 512, 145);
    c.font = "700 64px 'JetBrains Mono', monospace"; c.fillStyle = "#22c55e"; c.fillText("90:00  ·  EN DIRECTO", 512, 310);
  });
}

function adsTexture(): THREE.CanvasTexture {
  const t = canvasTex(2048, 128, (c) => {
    const ads = ["YTAUTO", "SHORTS", "REELS", "TIKTOK", "9:16", "GOL"];
    for (let i = 0; i < 12; i++) {
      c.fillStyle = i % 2 ? "#0ea5e9" : "#111827"; c.fillRect(i * 171, 0, 171, 128);
      c.font = "900 46px Impact, 'Arial Narrow', sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
      c.fillStyle = i % 2 ? "#ffffff" : "#facc15"; c.fillText(ads[i % ads.length], i * 171 + 85, 66);
    }
  });
  t.wrapS = THREE.RepeatWrapping;
  return t;
}

function Goal({ x }: { x: number }) {
  const post = <meshStandardMaterial color="#ffffff" roughness={0.3} />;
  return (
    <group position={[x, FLOOR_Y, 0]} rotation={[0, x > 0 ? -Math.PI / 2 : Math.PI / 2, 0]}>
      {[-3.6, 3.6].map((z) => <mesh key={z} position={[z, 1.2, 0]}><cylinderGeometry args={[0.09, 0.09, 2.4, 10]} />{post}</mesh>)}
      <mesh position={[0, 2.4, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.09, 0.09, 7.3, 10]} />{post}</mesh>
      <mesh position={[0, 1.2, -1]}><boxGeometry args={[7.2, 2.4, 0.02]} /><meshStandardMaterial color="#e5e7eb" transparent opacity={0.25} wireframe /></mesh>
    </group>
  );
}

export function Stadium({ active }: { active: boolean }) {
  const pitch = useMemo(pitchTexture, []);
  const score = useMemo(scoreTexture, []);
  const ads = useMemo(adsTexture, []);
  useFrame((_, dt) => { ads.offset.x += dt * 0.04; });
  return (
    <>
      <fog attach="fog" args={["#06120b", 60, 160]} />
      <color attach="background" args={["#030806"]} />
      <Stars radius={120} depth={30} count={1800} factor={4} fade speed={0.4} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y, 0]} receiveShadow>
        <planeGeometry args={[66, 44]} />
        <meshStandardMaterial map={pitch} roughness={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y - 0.05, 0]}>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#1c3d26" roughness={1} />
      </mesh>
      {[-1, 1].map((s) => <Goal key={s} x={s * 31} />)}
      {([0, 1, 2, 3] as const).map((s) => <Crowd key={s} side={s} active={active} />)}
      {[[-36, -26], [36, -26], [-36, 26], [36, 26]].map(([x, z], i) => <FloodLight key={i} position={[x, FLOOR_Y, z]} />)}
      {[0, 1, 2, 3].map((i) => {
        const pos: [number, number, number][] = [[0, FLOOR_Y + 0.6, -23.5], [0, FLOOR_Y + 0.6, 23.5], [-33.5, FLOOR_Y + 0.6, 0], [33.5, FLOOR_Y + 0.6, 0]];
        const rot = [0, Math.PI, Math.PI / 2, -Math.PI / 2][i];
        return (
          <mesh key={i} position={pos[i]} rotation={[0, rot, 0]}>
            <planeGeometry args={[i < 2 ? 64 : 42, 1.2]} />
            <meshBasicMaterial map={ads} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
        );
      })}
      <group position={[0, 10, -34]}>
        <mesh position={[0, 0, -0.3]}><boxGeometry args={[21, 9, 0.5]} /><meshStandardMaterial color="#111827" /></mesh>
        <mesh><planeGeometry args={[20, 7.8]} /><meshBasicMaterial map={score} toneMapped={false} /></mesh>
        <mesh position={[0, -8, -0.4]}><boxGeometry args={[0.6, 8, 0.6]} /><meshStandardMaterial color="#6b7280" /></mesh>
      </group>
      <hemisphereLight args={["#dbeafe", "#14532d", 0.8]} />
      <directionalLight position={[0, 30, 10]} intensity={2.4} color="#f8fafc" castShadow />
      <pointLight position={[-30, 22, -22]} intensity={300} distance={90} color="#fffbe6" />
      <pointLight position={[30, 22, -22]} intensity={300} distance={90} color="#fffbe6" />
      <pointLight position={[0, 22, 26]} intensity={260} distance={90} color="#fffbe6" />
      {active && <Sparkles count={70} scale={[60, 10, 40]} position={[0, 8, 0]} size={4} speed={0.5} color="#facc15" />}
    </>
  );
}

/* =================================================================================== puestos de trabajo */

function screenTex(glyph: string, color: string, profile: string): THREE.CanvasTexture {
  return canvasTex(256, 160, (c) => {
    const bg = profile === "kids" ? "#ffffff" : profile === "deportes" ? "#04120a" : "#160a26";
    c.fillStyle = bg; c.fillRect(0, 0, 256, 160);
    c.fillStyle = color; c.fillRect(0, 0, 256, 18);
    c.globalAlpha = 0.35;
    for (let i = 0; i < 6; i++) { c.fillRect(16, 34 + i * 18, 110 + rnd(i) * 100, 7); }
    c.globalAlpha = 1;
    c.font = "70px sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillText(glyph, 200, 100);
  });
}

function Station({ profile, color, glyph, active }: { profile: string; color: string; glyph: string; active: boolean }) {
  const tex = useMemo(() => screenTex(glyph, color, profile), [glyph, color, profile]);
  const screen = useRef<THREE.MeshBasicMaterial>(null);
  useFrame(({ clock }) => { if (screen.current) screen.current.color.setScalar(active ? 0.85 + Math.sin(clock.elapsedTime * 6) * 0.15 : 0.75); });
  const desk = profile === "kids" ? color : profile === "deportes" ? "#1f2937" : "#1a1026";
  const edge = profile === "kids" ? "#ffffff" : color;
  return (
    <group position={[0, 0, -1.5]}>
      {profile === "kids" ? (
        <mesh position={[0, 0.45, 0]} castShadow><cylinderGeometry args={[1.1, 1.1, 0.16, 32]} /><meshStandardMaterial color={desk} roughness={0.5} /></mesh>
      ) : (
        <mesh position={[0, 0.45, 0]} castShadow><boxGeometry args={[2.4, 0.12, 1]} /><meshStandardMaterial color={desk} roughness={0.4} metalness={0.2} /></mesh>
      )}
      {profile !== "kids" && <mesh position={[0, 0.39, 0.5]}><boxGeometry args={[2.4, 0.04, 0.03]} /><meshBasicMaterial color={edge} toneMapped={false} /></mesh>}
      {[-0.9, 0.9].map((x) => <mesh key={x} position={[x, 0.2, 0]}><cylinderGeometry args={[0.06, 0.06, 0.45, 8]} /><meshStandardMaterial color={profile === "kids" ? "#ffffff" : "#4b5563"} /></mesh>)}
      <group position={[0, 1.05, -0.25]} rotation={[-0.12, 0, 0]}>
        <mesh position={[0, 0, -0.03]}><boxGeometry args={[1.5, 0.95, 0.05]} /><meshStandardMaterial color="#0b0b10" /></mesh>
        <mesh><planeGeometry args={[1.4, 0.86]} /><meshBasicMaterial ref={screen} map={tex} toneMapped={false} /></mesh>
      </group>
      <mesh position={[0, 0.55, -0.25]}><cylinderGeometry args={[0.04, 0.06, 0.2, 8]} /><meshStandardMaterial color="#374151" /></mesh>
    </group>
  );
}

/** Puestos de trabajo de cada agente (misma disposición que la Baticueva) con su foco propio. */
export function ProfileStations({ profile, agents, colors, glyphs }: {
  profile: string; agents: Record<string, AgentState>; colors: Record<string, string>; glyphs: Record<string, string>;
}) {
  return (
    <>
      {Object.entries(HUB).map(([name, s]) => {
        const running = agents[name]?.status === "running";
        return (
          <group key={name} position={[s.x, FLOOR_Y, s.z]} rotation={[0, facingYaw(name), 0]} scale={HUB_SCALE}>
            <Station profile={profile} color={colors[name] ?? "#ffffff"} glyph={glyphs[name] ?? "★"} active={running} />
            <pointLight position={[0, 3.2, 0.6]} color={running ? colors[name] ?? "#ffffff" : profile === "kids" ? "#fff6e0" : "#e9d5ff"} intensity={running ? 34 : 10} distance={9} />
          </group>
        );
      })}
    </>
  );
}

/** Peana de cada personaje en los perfiles no LEGO: disco con el color del personaje y placa con su nombre. */
export function ProfileBase({ color, big = false, label = "", profile }: { color: string; big?: boolean; label?: string; profile: string }) {
  const r = big ? 1.5 : 1.05;
  const top = profile === "kids" ? color : profile === "deportes" ? "#0b2814" : "#1a0f2a";
  return (
    <group>
      <mesh position={[0, 0.06, 0]} castShadow receiveShadow><cylinderGeometry args={[r, r * 1.05, 0.12, 48]} /><meshStandardMaterial color={top} roughness={0.4} metalness={0.15} /></mesh>
      <mesh position={[0, 0.125, 0]} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[r - 0.12, r - 0.04, 48]} /><meshBasicMaterial color={profile === "kids" ? "#ffffff" : color} toneMapped={false} /></mesh>
      {label && <NamePlate label={label} z={r + 0.5} />}
    </group>
  );
}

export const WORLD_BACKGROUND: Record<string, string> = { gta6: "#120726", kids: "#bfe6ff", deportes: "#030806" };
