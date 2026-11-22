import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { canvasTex } from "./Batcave";
import type { AvatarSpec, Item } from "./avatars";
import { poseFor, type Pose } from "./pose";
import type { animationState } from "./pose";

type AnimSource = () => ReturnType<typeof animationState>;

const mats = new Map<string, THREE.MeshStandardMaterial>();
/** Material «vinilo» compartido por color (pocos materiales aunque haya muchos personajes). */
function mat(color: string, opts: { rough?: number; metal?: number; emissive?: string } = {}): THREE.MeshStandardMaterial {
  const key = `${color}|${opts.rough ?? 0.5}|${opts.metal ?? 0}|${opts.emissive ?? ""}`;
  let m = mats.get(key);
  if (!m) {
    m = new THREE.MeshStandardMaterial({ color, roughness: opts.rough ?? 0.5, metalness: opts.metal ?? 0, emissive: opts.emissive ?? "#000000", emissiveIntensity: opts.emissive ? 0.9 : 0 });
    mats.set(key, m);
  }
  return m;
}
const BLACK = "#111216";
const WHITE = "#f8fafc";
const GOLD = "#e8b931";

function patternTexture(base: string, p: NonNullable<AvatarSpec["pattern"]>, number?: string): THREE.CanvasTexture {
  return canvasTex(256, 256, (c) => {
    c.fillStyle = base;
    c.fillRect(0, 0, 256, 256);
    c.fillStyle = p.color;
    if (p.kind === "stripes") for (let x = 0; x < 256; x += 48) c.fillRect(x, 0, 20, 256);
    if (p.kind === "dots") for (let y = 16; y < 256; y += 40) for (let x = 16 + (y % 80 ? 20 : 0); x < 256; x += 40) { c.beginPath(); c.arc(x, y, 7, 0, 7); c.fill(); }
    if (p.kind === "hawaiian") {
      for (let i = 0; i < 14; i++) {
        const x = (i * 97) % 256, y = (i * 61) % 256;
        for (let k = 0; k < 5; k++) { c.beginPath(); c.ellipse(x + Math.cos(k * 1.256) * 12, y + Math.sin(k * 1.256) * 12, 10, 6, k * 1.256, 0, 7); c.fill(); }
        c.fillStyle = "#fff7d6"; c.beginPath(); c.arc(x, y, 5, 0, 7); c.fill(); c.fillStyle = p.color;
      }
    }
    if (number) numberOn(c, number);
  });
}

function numberOn(c: CanvasRenderingContext2D, n: string) {
  c.font = "900 120px Impact, 'Arial Black', sans-serif";
  c.textAlign = "center";
  c.textBaseline = "middle";
  c.lineWidth = 10;
  c.strokeStyle = "#111";
  c.strokeText(n, 128, 140);
  c.fillStyle = "#fff";
  c.fillText(n, 128, 140);
}

function jerseyTexture(base: string, number: string): THREE.CanvasTexture {
  return canvasTex(256, 256, (c) => { c.fillStyle = base; c.fillRect(0, 0, 256, 256); if (number) numberOn(c, number); });
}

/** Objeto en la mano derecha (o en la cabeza/cuerpo según el objeto). */
function HandItem({ item }: { item: Item }) {
  switch (item) {
    case "camera":
      return (<group position={[0, -0.05, 0.14]}><mesh material={mat(BLACK)}><boxGeometry args={[0.26, 0.18, 0.16]} /></mesh>
        <mesh position={[0, 0, 0.11]} rotation={[Math.PI / 2, 0, 0]} material={mat("#334155", { metal: 0.6, rough: 0.2 })}><cylinderGeometry args={[0.06, 0.07, 0.1, 16]} /></mesh>
        <mesh position={[0.07, 0.11, 0]} material={mat("#ef4444", { emissive: "#ef4444" })}><sphereGeometry args={[0.02, 8, 8]} /></mesh></group>);
    case "mic":
      return (<group position={[0, 0.02, 0.1]} rotation={[0.5, 0, 0]}><mesh material={mat(BLACK)}><cylinderGeometry args={[0.03, 0.025, 0.24, 12]} /></mesh>
        <mesh position={[0, 0.15, 0]} material={mat("#9ca3af", { metal: 0.7, rough: 0.3 })}><sphereGeometry args={[0.065, 16, 16]} /></mesh></group>);
    case "clipboard":
      return (<group position={[0, -0.05, 0.12]} rotation={[-0.3, 0, 0]}><mesh material={mat("#8b5a2b")}><boxGeometry args={[0.28, 0.36, 0.03]} /></mesh>
        <mesh position={[0, -0.02, 0.02]} material={mat(WHITE)}><boxGeometry args={[0.23, 0.28, 0.01]} /></mesh>
        <mesh position={[0, 0.17, 0.02]} material={mat("#9ca3af", { metal: 0.8 })}><boxGeometry args={[0.12, 0.05, 0.02]} /></mesh></group>);
    case "whistle":
      return (<mesh position={[0, 0, 0.1]} rotation={[0, 0, Math.PI / 2]} material={mat("#cbd5e1", { metal: 0.9, rough: 0.2 })}><cylinderGeometry args={[0.04, 0.04, 0.14, 12]} /></mesh>);
    case "phone":
      return (<group position={[0, 0.02, 0.1]} rotation={[-0.6, 0, 0]}><mesh material={mat(BLACK)}><boxGeometry args={[0.13, 0.24, 0.02]} /></mesh>
        <mesh position={[0, 0, 0.012]} material={mat("#38bdf8", { emissive: "#38bdf8" })}><planeGeometry args={[0.11, 0.2]} /></mesh></group>);
    case "briefcase":
      return (<group position={[0, -0.2, 0]}><mesh material={mat("#5b3a1e")}><boxGeometry args={[0.36, 0.26, 0.1]} /></mesh>
        <mesh position={[0, 0.16, 0]} material={mat(BLACK)}><torusGeometry args={[0.06, 0.015, 8, 16, Math.PI]} /></mesh></group>);
    case "megaphone":
      return (<mesh position={[0, 0.04, 0.2]} rotation={[Math.PI / 2, 0, 0]} material={mat(WHITE)}><coneGeometry args={[0.14, 0.34, 20, 1, true]} /></mesh>);
    case "book":
      return (<mesh position={[0, -0.04, 0.1]} rotation={[-0.4, 0, 0]} material={mat("#b91c1c")}><boxGeometry args={[0.26, 0.32, 0.06]} /></mesh>);
    case "flag":
      return (<group><mesh position={[0, 0.3, 0]} material={mat("#a16207")}><cylinderGeometry args={[0.015, 0.015, 0.9, 8]} /></mesh>
        <mesh position={[0.16, 0.62, 0]} material={mat("#facc15")}><boxGeometry args={[0.3, 0.2, 0.01]} /></mesh></group>);
    case "trophy":
      return (<group position={[0, 0.06, 0.1]}><mesh position={[0, 0.12, 0]} material={mat(GOLD, { metal: 0.9, rough: 0.25 })}><cylinderGeometry args={[0.12, 0.05, 0.18, 20]} /></mesh>
        <mesh material={mat(GOLD, { metal: 0.9, rough: 0.25 })}><cylinderGeometry args={[0.025, 0.025, 0.1, 8]} /></mesh>
        <mesh position={[0, -0.06, 0]} material={mat("#1f2937")}><boxGeometry args={[0.14, 0.05, 0.14]} /></mesh></group>);
    case "binoculars":
      return (<group position={[0, 0.04, 0.12]} rotation={[Math.PI / 2, 0, 0]}>{[-0.06, 0.06].map((x) => (
        <mesh key={x} position={[x, 0, 0]} material={mat(BLACK)}><cylinderGeometry args={[0.045, 0.05, 0.16, 12]} /></mesh>))}</group>);
    case "laptop":
      return (<group position={[0, -0.1, 0.18]}><mesh material={mat("#9ca3af", { metal: 0.6 })}><boxGeometry args={[0.36, 0.02, 0.24]} /></mesh>
        <mesh position={[0, 0.12, -0.12]} rotation={[-0.25, 0, 0]} material={mat("#60a5fa", { emissive: "#60a5fa" })}><boxGeometry args={[0.36, 0.24, 0.01]} /></mesh></group>);
    case "drum":
      return (<group position={[-0.36, 0.1, 0.25]}><mesh material={mat("#dc2626")}><cylinderGeometry args={[0.2, 0.2, 0.22, 24]} /></mesh>
        <mesh position={[0, 0.115, 0]} material={mat(WHITE)}><cylinderGeometry args={[0.2, 0.2, 0.01, 24]} /></mesh></group>);
    case "balloon":
      return (<group><mesh position={[0, 0.6, 0]} material={mat("#ef4444", { rough: 0.25 })}><sphereGeometry args={[0.2, 20, 20]} /></mesh>
        <mesh position={[0, 0.25, 0]} material={mat(WHITE)}><cylinderGeometry args={[0.004, 0.004, 0.6, 4]} /></mesh></group>);
    case "bone":
      return (<group position={[0, 0, 0.1]} rotation={[0, 0, Math.PI / 2]}><mesh material={mat("#f5f0e1")}><cylinderGeometry args={[0.03, 0.03, 0.24, 8]} /></mesh>
        {[-0.13, 0.13].map((y) => <mesh key={y} position={[0, y, 0]} material={mat("#f5f0e1")}><sphereGeometry args={[0.05, 10, 10]} /></mesh>)}</group>);
    case "stethoscope":
    case "headphones":
    case "cards":
      return null; // se dibujan en el cuello / la cabeza
  }
}

/** Personaje chibi animado con el estado real del agente. Pies en el origen; mira hacia +Z. */
export function Avatar({ spec, getAnim, seed = 0, yaw = 0, turnToWork = false }: {
  spec: AvatarSpec; getAnim: AnimSource; seed?: number; yaw?: number; turnToWork?: boolean;
}) {
  const root = useRef<THREE.Group>(null);
  const upper = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const cur = useRef<Pose | null>(null);
  const yawRef = useRef(yaw);
  const s = spec;
  const animal = s.head !== "human" && s.head !== "baby";
  const headR = s.head === "baby" ? 0.46 : animal ? 0.42 : 0.4;
  const torsoTex = useMemo(() => {
    if (s.topStyle === "jersey") return s.pattern ? patternTexture(s.top, s.pattern, s.number) : jerseyTexture(s.top, s.number ?? "");
    return s.pattern ? patternTexture(s.top, s.pattern) : null;
  }, [s]);
  const torsoMat = useMemo(() => (torsoTex ? new THREE.MeshStandardMaterial({ map: torsoTex, roughness: 0.6 }) : mat(s.top, { rough: 0.6 })), [torsoTex, s.top]);
  const longSleeve = ["shirt", "suit", "hoodie", "coat"].includes(s.topStyle);
  const skin = mat(s.skin, { rough: 0.45 });
  const sleeve = s.topStyle === "tank" || s.topStyle === "overalls" ? skin : torsoMat;

  useFrame((st, dt) => {
    const { state, sinceFinish } = getAnim();
    const target = poseFor(state, st.clock.elapsedTime, seed, sinceFinish);
    const k = 1 - Math.exp(-dt * 9);
    const l = (a: number, b: number) => a + (b - a) * k;
    const c = cur.current ?? target;
    const n: Pose = {
      bodyY: l(c.bodyY, target.bodyY), bodyYaw: l(c.bodyYaw, target.bodyYaw), headYaw: l(c.headYaw, target.headYaw), headPitch: l(c.headPitch, target.headPitch),
      legL: l(c.legL, target.legL), legR: l(c.legR, target.legR), cape: c.cape, lean: l(c.lean, target.lean),
      armL: { x: l(c.armL.x, target.armL.x), spread: l(c.armL.spread, target.armL.spread) },
      armR: { x: l(c.armR.x, target.armR.x), spread: l(c.armR.spread, target.armR.spread) },
    };
    cur.current = n;
    const targetYaw = yaw + (turnToWork && state === "work" ? Math.PI : 0);
    yawRef.current += (targetYaw - yawRef.current) * (1 - Math.exp(-dt * 4));
    if (root.current) { root.current.position.y = n.bodyY * 2.2; root.current.rotation.y = yawRef.current + n.bodyYaw; }
    if (upper.current) upper.current.rotation.x = n.lean;
    if (head.current) { head.current.rotation.y = n.headYaw; head.current.rotation.x = n.headPitch; }
    if (armL.current) { armL.current.rotation.x = n.armL.x; armL.current.rotation.z = -(0.12 + n.armL.spread); }
    if (armR.current) { armR.current.rotation.x = n.armR.x; armR.current.rotation.z = 0.12 + n.armR.spread; }
    if (legL.current) legL.current.rotation.x = n.legL;
    if (legR.current) legR.current.rotation.x = n.legR;
  });

  const eyeY = animal ? 0.08 : 0.04;
  const eyeX = s.head === "baby" ? 0.15 : 0.14;
  const eyeR = s.head === "human" ? 0.075 : 0.095;
  return (
    <group ref={root} scale={s.scale ?? 1}>
      {/* piernas */}
      {[-1, 1].map((side) => (
        <group key={side} ref={side < 0 ? legL : legR} position={[side * 0.15, 0.62, 0]}>
          <mesh position={[0, -0.26, 0]} material={s.topStyle === "dress" ? skin : mat(s.bottom, { rough: 0.65 })} castShadow><capsuleGeometry args={[0.12, 0.3, 6, 12]} /></mesh>
          <mesh position={[0, -0.55, 0.05]} material={mat(s.shoes, { rough: 0.4 })} castShadow><boxGeometry args={[0.24, 0.13, 0.34]} /></mesh>
        </group>
      ))}
      <group ref={upper} position={[0, 0.66, 0]}>
        {/* cadera y torso */}
        <mesh position={[0, 0.02, 0]} material={mat(s.bottom, { rough: 0.65 })} castShadow><boxGeometry args={[0.56, 0.2, 0.36]} /></mesh>
        {s.topStyle === "dress" ? (
          <mesh position={[0, 0.3, 0]} material={torsoMat} castShadow><cylinderGeometry args={[0.27, 0.46, 0.72, 24]} /></mesh>
        ) : (
          <RoundedBox args={[0.64, 0.62, 0.4]} radius={0.12} smoothness={3} position={[0, 0.38, 0]} material={torsoMat} castShadow />
        )}
        {s.topStyle === "suit" && (<>
          <mesh position={[0, 0.48, 0.205]} material={mat(WHITE)}><planeGeometry args={[0.16, 0.36]} /></mesh>
          <mesh position={[0, 0.44, 0.21]} material={mat("#b91c1c")}><boxGeometry args={[0.06, 0.26, 0.01]} /></mesh>
        </>)}
        {s.topStyle === "coat" && <mesh position={[0, -0.06, 0]} material={torsoMat}><boxGeometry args={[0.62, 0.3, 0.38]} /></mesh>}
        {s.topStyle === "hoodie" && <mesh position={[0, 0.7, -0.16]} rotation={[0.4, 0, 0]} material={torsoMat}><torusGeometry args={[0.2, 0.08, 8, 20, Math.PI]} /></mesh>}
        {s.topStyle === "overalls" && [-0.17, 0.17].map((x) => <mesh key={x} position={[x, 0.55, 0.205]} material={mat(GOLD, { metal: 0.8 })}><cylinderGeometry args={[0.03, 0.03, 0.01, 10]} /></mesh>)}
        {s.chain && <mesh position={[0, 0.62, 0.12]} rotation={[1.2, 0, 0]} material={mat(GOLD, { metal: 0.95, rough: 0.2 })}><torusGeometry args={[0.17, 0.02, 8, 24]} /></mesh>}
        {s.item === "stethoscope" && <mesh position={[0, 0.6, 0.12]} rotation={[1.25, 0, 0]} material={mat("#374151", { metal: 0.5 })}><torusGeometry args={[0.18, 0.018, 8, 24]} /></mesh>}
        {s.item === "whistle" && <mesh position={[0, 0.55, 0.15]} rotation={[1.2, 0, 0]} material={mat("#111")}><torusGeometry args={[0.16, 0.01, 6, 20]} /></mesh>}
        {/* brazos */}
        {[-1, 1].map((side) => (
          <group key={side} ref={side < 0 ? armL : armR} position={[side * 0.38, 0.6, 0]}>
            <mesh position={[0, -0.1, 0]} material={sleeve} castShadow><capsuleGeometry args={[0.1, longSleeve ? 0.32 : 0.12, 6, 12]} /></mesh>
            {!longSleeve && <mesh position={[0, -0.3, 0]} material={skin} castShadow><capsuleGeometry args={[0.09, 0.16, 6, 12]} /></mesh>}
            <mesh position={[0, -0.47, 0]} material={animal ? mat(s.snout ?? s.skin) : skin} castShadow><sphereGeometry args={[0.1, 14, 14]} /></mesh>
            {side > 0 && s.item && <group position={[0, -0.5, 0.02]}><HandItem item={s.item} /></group>}
          </group>
        ))}
        {/* cabeza */}
        <group ref={head} position={[0, 0.72, 0]}>
          <mesh position={[0, 0.06, 0]} material={skin}><cylinderGeometry args={[0.1, 0.12, 0.12, 12]} /></mesh>
          <group position={[0, headR + 0.06, 0]}>
            <mesh material={skin} scale={s.head === "shark" ? [1, 1.18, 1.05] : s.head === "pig" ? [1.08, 0.98, 1] : [1, 1, 1]} castShadow>
              <sphereGeometry args={[headR, 32, 32]} />
            </mesh>
            {/* ojos y boca */}
            {[-1, 1].map((side) => (
              <group key={side} position={[side * eyeX, eyeY, headR * 0.86]}>
                <mesh material={mat(WHITE, { rough: 0.2 })}><sphereGeometry args={[eyeR, 14, 14]} /></mesh>
                <mesh position={[0, 0, eyeR * 0.62]} material={mat(BLACK, { rough: 0.15 })}><sphereGeometry args={[eyeR * 0.55, 12, 12]} /></mesh>
                <mesh position={[eyeR * 0.25, eyeR * 0.3, eyeR * 0.95]} material={mat(WHITE, { emissive: "#ffffff" })}><sphereGeometry args={[eyeR * 0.16, 8, 8]} /></mesh>
              </group>
            ))}
            {s.head !== "pig" && s.head !== "dog" && s.head !== "fox" && (
              <mesh position={[0, -0.13, headR * 0.9]} rotation={[0, 0, Math.PI]} material={mat("#7f1d1d")}><torusGeometry args={[0.09, 0.02, 8, 16, Math.PI]} /></mesh>
            )}
            {s.head === "dog" && (<>
              <mesh position={[0, -0.1, headR * 0.82]} scale={[1.2, 0.8, 1]} material={mat(s.snout ?? WHITE)}><sphereGeometry args={[0.17, 16, 16]} /></mesh>
              <mesh position={[0, -0.04, headR + 0.08]} material={mat(BLACK, { rough: 0.2 })}><sphereGeometry args={[0.06, 12, 12]} /></mesh>
              {[-1, 1].map((x) => <mesh key={x} position={[x * 0.24, 0.34, 0]} rotation={[0, 0, -x * 0.35]} material={mat(s.ears ?? s.skin)}><coneGeometry args={[0.12, 0.34, 4]} /></mesh>)}
            </>)}
            {s.head === "fox" && (<>
              <mesh position={[0, -0.08, headR * 0.86]} rotation={[Math.PI / 2, 0, 0]} material={mat(s.snout ?? WHITE)}><coneGeometry args={[0.14, 0.3, 16]} /></mesh>
              <mesh position={[0, -0.08, headR + 0.2]} material={mat(BLACK)}><sphereGeometry args={[0.045, 10, 10]} /></mesh>
              {[-1, 1].map((x) => <mesh key={x} position={[x * 0.22, 0.4, 0]} rotation={[0, 0, -x * 0.25]} material={mat(s.ears ?? s.skin)}><coneGeometry args={[0.13, 0.42, 4]} /></mesh>)}
            </>)}
            {s.head === "pig" && (<>
              <mesh position={[0, -0.06, headR * 0.98]} rotation={[Math.PI / 2, 0, 0]} material={mat(s.snout ?? s.skin)}><cylinderGeometry args={[0.13, 0.14, 0.14, 20]} /></mesh>
              {[-1, 1].map((x) => <mesh key={x} position={[x * 0.045, -0.06, headR + 0.06]} material={mat("#9d174d")}><sphereGeometry args={[0.025, 8, 8]} /></mesh>)}
              {[-1, 1].map((x) => <mesh key={x} position={[x * 0.22, 0.34, 0.02]} rotation={[0, 0, -x * 0.5]} material={mat(s.ears ?? s.skin)}><coneGeometry args={[0.09, 0.2, 10]} /></mesh>)}
            </>)}
            {s.head === "shark" && (<>
              <mesh position={[0, 0.5, -0.08]} rotation={[0, Math.PI / 2, 0]} scale={[1, 1, 0.35]} material={mat(s.skin)}><coneGeometry args={[0.2, 0.36, 3]} /></mesh>
              <mesh position={[0, -0.22, headR * 0.6]} scale={[1.1, 0.6, 0.7]} material={mat(s.snout ?? WHITE)}><sphereGeometry args={[0.3, 20, 16]} /></mesh>
              {[-0.12, -0.04, 0.04, 0.12].map((x) => <mesh key={x} position={[x, -0.2, headR * 0.98]} rotation={[0, 0, Math.PI]} material={mat(WHITE)}><coneGeometry args={[0.025, 0.06, 4]} /></mesh>)}
            </>)}
            {/* pelo */}
            {s.hair && s.hair.style !== "bald" && (() => {
              const h = mat(s.hair.color, { rough: 0.7 });
              const cap = <mesh position={[0, 0.12, -0.04]} scale={[1.05, s.hair.style === "slick" ? 0.5 : 0.62, 1.05]} material={h}><sphereGeometry args={[headR, 24, 16, 0, Math.PI * 2, 0, Math.PI / 1.7]} /></mesh>;
              switch (s.hair.style) {
                case "tuft": return <mesh position={[0, headR + 0.04, 0.05]} rotation={[0.3, 0, 0]} material={h}><coneGeometry args={[0.06, 0.18, 8]} /></mesh>;
                case "bun": return <>{cap}<mesh position={[0, 0.34, -0.3]} material={h}><sphereGeometry args={[0.14, 16, 16]} /></mesh></>;
                case "ponytail": return <>{cap}<mesh position={[0, -0.05, -0.42]} rotation={[0.35, 0, 0]} material={h}><capsuleGeometry args={[0.09, 0.4, 6, 10]} /></mesh></>;
                case "long": return <>{cap}<mesh position={[0, -0.2, -0.2]} material={h}><boxGeometry args={[0.8, 0.6, 0.36]} /></mesh></>;
                case "curly": return <>{[...Array(9)].map((_, i) => { const a = (i / 9) * Math.PI * 2; return <mesh key={i} position={[Math.cos(a) * 0.3, 0.25 + Math.sin(i * 1.7) * 0.05, Math.sin(a) * 0.3 - 0.05]} material={h}><sphereGeometry args={[0.15, 12, 12]} /></mesh>; })}</>;
                case "dreads": return <>{cap}{[...Array(10)].map((_, i) => { const a = Math.PI * 0.15 + (i / 9) * Math.PI * 0.7; return <mesh key={i} position={[Math.cos(a + Math.PI) * 0.36, -0.15, Math.sin(a + Math.PI) * 0.36]} material={h}><capsuleGeometry args={[0.04, 0.36, 4, 6]} /></mesh>; })}</>;
                default: return cap;
              }
            })()}
            {s.beard && <mesh position={[0, -0.2, 0.12]} scale={[1, 0.7, 0.9]} material={mat(s.beard, { rough: 0.8 })}><sphereGeometry args={[0.34, 20, 12, 0, Math.PI * 2, Math.PI / 2.2, Math.PI / 2]} /></mesh>}
            {s.glasses === "sun" && (<group position={[0, eyeY, headR * 0.96]}>
              {[-1, 1].map((x) => <mesh key={x} position={[x * eyeX, 0, 0.03]} material={mat(BLACK, { rough: 0.1, metal: 0.4 })}><boxGeometry args={[0.17, 0.1, 0.03]} /></mesh>)}
              <mesh material={mat(BLACK)}><boxGeometry args={[0.1, 0.02, 0.02]} /></mesh></group>)}
            {s.glasses === "round" && (<group position={[0, eyeY, headR * 0.98]}>
              {[-1, 1].map((x) => <mesh key={x} position={[x * eyeX, 0, 0.04]} material={mat(BLACK)}><torusGeometry args={[0.085, 0.014, 8, 20]} /></mesh>)}</group>)}
            {s.item === "headphones" && (<group>
              <mesh position={[0, 0.06, 0]} material={mat(BLACK)}><torusGeometry args={[headR + 0.04, 0.03, 8, 24, Math.PI]} /></mesh>
              {[-1, 1].map((x) => <mesh key={x} position={[x * (headR + 0.04), 0.02, 0]} rotation={[0, 0, Math.PI / 2]} material={mat("#ef4444")}><cylinderGeometry args={[0.1, 0.1, 0.08, 16]} /></mesh>)}</group>)}
            {/* sombreros */}
            {s.hat?.kind === "cap" && (<group position={[0, headR * 0.62, 0]}>
              <mesh material={mat(s.hat.color)}><sphereGeometry args={[headR * 1.02, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} /></mesh>
              <mesh position={[0, 0.0, headR * 0.95]} material={mat(s.hat.color)}><boxGeometry args={[0.42, 0.03, 0.3]} /></mesh></group>)}
            {s.hat?.kind === "beanie" && <mesh position={[0, headR * 0.45, 0]} material={mat(s.hat.color, { rough: 0.8 })}><sphereGeometry args={[headR * 1.05, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} /></mesh>}
            {s.hat?.kind === "police" && (<group position={[0, headR * 0.72, 0]}>
              <mesh material={mat(s.hat.color)}><cylinderGeometry args={[headR * 0.95, headR * 0.85, 0.2, 24]} /></mesh>
              <mesh position={[0, 0.0, headR * 0.7]} rotation={[0.3, 0, 0]} material={mat(BLACK)}><boxGeometry args={[0.4, 0.03, 0.22]} /></mesh>
              <mesh position={[0, 0.02, headR * 0.92]} material={mat(GOLD, { metal: 0.9 })}><circleGeometry args={[0.06, 12]} /></mesh></group>)}
            {s.hat?.kind === "cowboy" && (<group position={[0, headR * 0.7, 0]}>
              <mesh material={mat(s.hat.color)}><cylinderGeometry args={[headR * 1.7, headR * 1.7, 0.03, 32]} /></mesh>
              <mesh position={[0, 0.14, 0]} material={mat(s.hat.color)}><cylinderGeometry args={[headR * 0.75, headR * 0.85, 0.28, 24]} /></mesh></group>)}
            {s.hat?.kind === "headband" && <mesh position={[0, headR * 0.55, 0]} rotation={[Math.PI / 2, 0, 0]} material={mat(s.hat.color)}><torusGeometry args={[headR * 0.86, 0.04, 8, 32]} /></mesh>}
          </group>
        </group>
      </group>
    </group>
  );
}
