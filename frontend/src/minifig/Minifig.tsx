/**
 * Plantilla ÚNICA de minifigura LEGO Batman. Los nueve personajes se construyen aquí con la misma
 * geometría (`BODY`), el mismo material de plástico y la misma animación; la variante solo aporta
 * colores, estampados y accesorios.
 */
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { drawOps } from "./ops";
import { poseFor, type Pose } from "./pose";
import { BODY, HEAD_Y, MATERIAL, PLASTIC, SHOULDER_Y, type AnimationState } from "./styleBible";
import type { Accessory, Variant } from "./variants";

const materials = new Map<string, THREE.MeshPhysicalMaterial>();
/** Un único material de plástico por color: mismo brillo y barniz para todos. */
export function plastic(color: string): THREE.MeshPhysicalMaterial {
  let m = materials.get(color);
  if (!m) {
    m = new THREE.MeshPhysicalMaterial({ color, ...MATERIAL });
    materials.set(color, m);
  }
  return m;
}

function printTexture(ops: Parameters<typeof drawOps>[1], transparent: boolean): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const ctx = c.getContext("2d")!;
  if (!transparent) ctx.clearRect(0, 0, 256, 256);
  drawOps(ctx as unknown as Parameters<typeof drawOps>[0], ops, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

function Cyl({ r, h, color, pos, rot, seg = 24, cast = true }: { r: number; h: number; color: string; pos?: [number, number, number]; rot?: [number, number, number]; seg?: number; cast?: boolean }) {
  return (
    <mesh position={pos} rotation={rot} castShadow={cast} material={plastic(color)}>
      <cylinderGeometry args={[r, r, h, seg]} />
    </mesh>
  );
}

function Box({ w, h, d, color, pos }: { w: number; h: number; d: number; color: string; pos?: [number, number, number] }) {
  return (
    <mesh position={pos} castShadow material={plastic(color)}>
      <boxGeometry args={[w, h, d]} />
    </mesh>
  );
}

/** Mano en forma de pinza (C). */
function Hand({ color, y }: { color: string; y: number }) {
  return (
    <group position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <mesh rotation={[0, 0, Math.PI / 2 - 1.775 * Math.PI]} castShadow material={plastic(color)}>
        <torusGeometry args={[BODY.hand.r, BODY.hand.tube, 10, 20, BODY.hand.arc]} />
      </mesh>
    </group>
  );
}

function Cone({ r, h, color, pos, rot }: { r: number; h: number; color: string; pos: [number, number, number]; rot?: [number, number, number] }) {
  return (
    <mesh position={pos} rotation={rot} castShadow material={plastic(color)}>
      <coneGeometry args={[r, h, 4]} />
    </mesh>
  );
}

function Dome({ color, y, sy = 0.55 }: { color: string; y: number; sy?: number }) {
  return (
    <mesh position={[0, y, 0]} scale={[1, sy, 1]} castShadow material={plastic(color)}>
      <sphereGeometry args={[BODY.head.r + 0.014, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2]} />
    </mesh>
  );
}

function HeadAccessory({ a }: { a: Accessory }) {
  const H = BODY.head.h;
  const R = BODY.head.r;
  switch (a.t) {
    case "ears": {
      const tall = a.kind === "bat" ? 0.2 : 0.13;
      const w = a.kind === "bat" ? 0.06 : 0.075;
      return (
        <>
          {[-1, 1].map((s) => (
            <Cone key={s} r={w} h={tall} color={a.color} pos={[s * 0.115, H + tall / 2 - 0.02, 0.0]} rot={[0, Math.PI / 4, -s * 0.12]} />
          ))}
        </>
      );
    }
    case "hair":
      if (a.style === "joker")
        return (
          <>
            <Dome color={a.a} y={H - 0.05} />
            {[-0.12, -0.06, 0, 0.06, 0.12].map((x, i) => (
              <Cone key={i} r={0.035} h={0.16} color={a.a} pos={[x, H + 0.1, -0.02 - Math.abs(x) * 0.2]} rot={[-0.5, 0, -x * 3]} />
            ))}
          </>
        );
      if (a.style === "nightwing")
        return (
          <>
            <Dome color={a.a} y={H - 0.05} />
            <Cone r={0.05} h={0.12} color={a.a} pos={[0.04, H + 0.1, 0.06]} rot={[0.9, 0, -0.4]} />
          </>
        );
      return (
        <>
          <Dome color="#F5E6A8" y={H - 0.05} />
          {[-1, 1].map((s) => (
            <group key={s} position={[s * 0.25, H - 0.06, -0.02]}>
              <mesh castShadow material={plastic(s < 0 ? a.a : a.b ?? a.a)}>
                <sphereGeometry args={[0.075, 16, 12]} />
              </mesh>
              <Cone r={0.06} h={0.18} color={s < 0 ? a.a : a.b ?? a.a} pos={[s * 0.07, -0.12, 0]} rot={[0, Math.PI / 4, s * 0.5]} />
            </group>
          ))}
        </>
      );
    case "hat": {
      const crown = a.style === "top" ? 0.22 : 0.1;
      return (
        <group position={[0, H, 0]}>
          <Cyl r={0.25} h={0.025} color={a.color} pos={[0, 0.012, 0]} seg={32} />
          {a.style === "top" ? <Cyl r={0.155} h={crown} color={a.color} pos={[0, crown / 2, 0]} seg={28} /> : (
            <mesh position={[0, 0.02, 0]} scale={[1, 0.8, 1]} castShadow material={plastic(a.color)}>
              <sphereGeometry args={[0.17, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
            </mesh>
          )}
          <Cyl r={0.158} h={0.035} color={a.band} pos={[0, 0.05, 0]} seg={28} cast={false} />
        </group>
      );
    }
    case "monocle":
      return (
        <mesh position={[0.07, H * 0.58, R + 0.006]} material={plastic("#C9A227")}>
          <torusGeometry args={[0.035, 0.006, 8, 20]} />
        </mesh>
      );
    case "baneMask":
      return (
        <group>
          <Box w={0.2} h={0.1} d={0.07} color={PLASTIC.grey} pos={[0, 0.075, R + 0.012]} />
          {[-1, 1].map((s) => (
            <Cyl key={s} r={0.018} h={0.2} color={PLASTIC.black} pos={[s * 0.15, 0.13, R - 0.03]} rot={[0.3, 0, s * 0.25]} seg={10} />
          ))}
          <Box w={0.18} h={0.022} d={0.05} color={PLASTIC.black} pos={[0, 0.075, R + 0.047]} />
        </group>
      );
    default:
      return null;
  }
}

function Torso({ v }: { v: Variant }) {
  const T = BODY.torso;
  const tex = useMemo(() => printTexture(v.torso, false), [v]);
  useEffect(() => () => tex.dispose(), [tex]);
  const rb = (T.wBottom / 2) * Math.SQRT2;
  const rt = (T.wTop / 2) * Math.SQRT2;
  return (
    <group position={[0, BODY.legs.h + BODY.hips.h + T.h / 2, 0]}>
      {/* la escala (profundidad) va en el grupo y el giro de 45° en la malla: así el torso queda alineado con los ejes */}
      <group scale={[1, 1, T.d / T.wBottom]}>
        <mesh rotation={[0, Math.PI / 4, 0]} castShadow material={plastic(v.torsoColor)}>
          <cylinderGeometry args={[rt, rb, T.h, 4, 1]} />
        </mesh>
      </group>
      <mesh position={[0, 0, T.d / 2 + 0.003]} rotation={[-0.04, 0, 0]}>
        <planeGeometry args={[(T.wBottom + T.wTop) / 2 - 0.005, T.h - 0.005]} />
        <meshPhysicalMaterial map={tex} {...MATERIAL} />
      </mesh>
    </group>
  );
}

function Head({ v, headRef }: { v: Variant; headRef: React.RefObject<THREE.Group | null> }) {
  const R = BODY.head.r;
  const H = BODY.head.h;
  const tex = useMemo(() => printTexture(v.face, true), [v]);
  useEffect(() => () => tex.dispose(), [tex]);
  const hasHat = v.accessories.some((a) => a.t === "hat");
  return (
    <group ref={headRef} position={[0, HEAD_Y, 0]}>
      <Cyl r={R} h={H} color={v.head} pos={[0, H / 2, 0]} seg={40} />
      {!hasHat && <Cyl r={BODY.headStud.r} h={BODY.headStud.h} color={v.head} pos={[0, H + BODY.headStud.h / 2, 0]} seg={20} />}
      <mesh position={[0, H / 2, 0]}>
        <cylinderGeometry args={[R + 0.002, R + 0.002, H, 32, 1, true, -0.6, 1.2]} />
        <meshPhysicalMaterial map={tex} transparent alphaTest={0.02} {...MATERIAL} />
      </mesh>
      {v.accessories.map((a, i) => <HeadAccessory key={i} a={a} />)}
    </group>
  );
}

export interface AnimSource {
  (): { state: AnimationState; sinceFinish: number };
}

export function Minifig({ variant: v, getAnim, seed = 0 }: { variant: Variant; getAnim: AnimSource; seed?: number }) {
  const root = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const cape = useRef<THREE.Group>(null);
  const cur = useRef<Pose | null>(null);
  const capeSpec = v.accessories.find((a): a is Extract<Accessory, { t: "cape" }> => a.t === "cape");
  const umbrella = v.accessories.find((a): a is Extract<Accessory, { t: "umbrella" }> => a.t === "umbrella");

  useFrame((s, dt) => {
    const { state, sinceFinish } = getAnim();
    const target = poseFor(state, s.clock.elapsedTime, seed, sinceFinish);
    const k = Math.min(1, dt * 10); // suaviza el paso de un estado a otro
    const lerp = (a: number, b: number) => a + (b - a) * k;
    const c = cur.current ?? target;
    const n: Pose = {
      bodyY: lerp(c.bodyY, target.bodyY), bodyYaw: lerp(c.bodyYaw, target.bodyYaw), headYaw: lerp(c.headYaw, target.headYaw),
      headPitch: lerp(c.headPitch, target.headPitch), legL: lerp(c.legL, target.legL), legR: lerp(c.legR, target.legR), cape: lerp(c.cape, target.cape),
      armL: { x: lerp(c.armL.x, target.armL.x), z: lerp(c.armL.z, target.armL.z) },
      armR: { x: lerp(c.armR.x, target.armR.x), z: lerp(c.armR.z, target.armR.z) },
    };
    cur.current = n;
    if (root.current) { root.current.position.y = n.bodyY; root.current.rotation.y = n.bodyYaw; }
    if (head.current) { head.current.rotation.y = n.headYaw; head.current.rotation.x = n.headPitch; }
    if (armL.current) { armL.current.rotation.x = n.armL.x; armL.current.rotation.z = n.armL.z; }
    if (armR.current) { armR.current.rotation.x = n.armR.x; armR.current.rotation.z = n.armR.z; }
    if (legL.current) legL.current.rotation.x = n.legL;
    if (legR.current) legR.current.rotation.x = n.legR;
    if (cape.current) cape.current.rotation.x = n.cape;
  });

  const L = BODY.legs;
  const A = BODY.arm;
  return (
    <group ref={root}>
      {/* piernas (pivotan en la cadera) y cadera */}
      <group ref={legL} position={[-L.x, L.h, 0]}><Box w={L.w} h={L.h} d={L.d} color={v.legs.l} pos={[0, -L.h / 2, 0]} /></group>
      <group ref={legR} position={[L.x, L.h, 0]}><Box w={L.w} h={L.h} d={L.d} color={v.legs.r} pos={[0, -L.h / 2, 0]} /></group>
      <Box w={BODY.hips.w} h={BODY.hips.h} d={BODY.hips.d} color={v.hips} pos={[0, L.h + BODY.hips.h / 2, 0]} />
      <Torso v={v} />
      <Cyl r={BODY.neck.r} h={BODY.neck.h} color={v.head === PLASTIC.black ? PLASTIC.black : PLASTIC.skin} pos={[0, HEAD_Y - BODY.neck.h / 2, 0]} seg={16} />
      {/* brazos: cilindro recto de una pieza + mano en pinza */}
      <group ref={armL} position={[-A.shoulderX, SHOULDER_Y, 0]}>
        <Cyl r={A.r} h={A.len} color={v.arms.l} pos={[0, -A.len / 2, 0]} seg={16} />
        <Hand color={v.hands} y={-A.len - 0.01} />
      </group>
      <group ref={armR} position={[A.shoulderX, SHOULDER_Y, 0]}>
        <Cyl r={A.r} h={A.len} color={v.arms.r} pos={[0, -A.len / 2, 0]} seg={16} />
        <Hand color={v.hands} y={-A.len - 0.01} />
        {umbrella && (
          <group position={[0, -A.len - 0.01, 0.02]}>
            <Cyl r={0.012} h={0.85} color={PLASTIC.darkGrey} pos={[0, -0.18, 0]} seg={8} />
            <mesh position={[0, 0.3, 0]} rotation={[Math.PI, 0, 0]} castShadow material={plastic(umbrella.color)}>
              <coneGeometry args={[0.07, 0.46, 12]} />
            </mesh>
            <mesh position={[0.04, 0.52, 0]} rotation={[0, 0, Math.PI]} material={plastic(PLASTIC.darkGrey)}>
              <torusGeometry args={[0.04, 0.011, 8, 14, Math.PI]} />
            </mesh>
          </group>
        )}
      </group>
      <Head v={v} headRef={head} />
      {v.accessories.some((a) => a.t === "flower") && (
        <mesh position={[0.1, SHOULDER_Y - 0.08, BODY.torso.d / 2 + 0.02]} material={plastic((v.accessories.find((a) => a.t === "flower") as { color: string }).color)}>
          <sphereGeometry args={[0.035, 12, 10]} />
        </mesh>
      )}
      {capeSpec && (
        <group ref={cape} position={[0, SHOULDER_Y + 0.02, -BODY.torso.d / 2 - 0.02]}>
          <Box w={0.64} h={0.85} d={0.016} color={capeSpec.outer} pos={[0, -0.42, -0.008]} />
          <Box w={0.62} h={0.83} d={0.012} color={capeSpec.inner} pos={[0, -0.42, 0.004]} />
        </group>
      )}
    </group>
  );
}
