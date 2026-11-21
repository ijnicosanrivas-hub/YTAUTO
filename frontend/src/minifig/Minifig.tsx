/**
 * Plantilla ÚNICA de minifigura LEGO Batman (v2). Geometría en LDU a partir de las piezas oficiales
 * (ver `styleBible.ts`): torso trapecial biselado, cabeza torneada con taco hueco, brazos inclinados 9,8°,
 * manos en pinza, cadera y piernas de ladrillo. La variante solo aporta colores, estampados y accesorios.
 */
import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { drawOps } from "./ops";
import { poseFor, type Pose } from "./pose";
import { BODY, HEAD_BASE_Y, HIPS_TOP_Y, LDU, LEG_TOP_Y, MATERIAL, PLASTIC, SHOULDER_Y, type AnimationState } from "./styleBible";
import type { Accessory, Variant } from "./variants";

const materials = new Map<string, THREE.MeshPhysicalMaterial>();
/** Un único material de plástico ABS por color: mismo brillo y barniz para todas las piezas de la escena. */
export function plastic(color: string): THREE.MeshPhysicalMaterial {
  let m = materials.get(color);
  if (!m) {
    m = new THREE.MeshPhysicalMaterial({ color, ...MATERIAL });
    materials.set(color, m);
  }
  return m;
}

const POSE_Y = 75; // LDU por unidad de salto de la pose

function printTexture(ops: Parameters<typeof drawOps>[1]): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  drawOps(c.getContext("2d") as unknown as Parameters<typeof drawOps>[0], ops, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// --- geometrías compartidas (una sola vez) ---------------------------------------------------
function headGeometry(): THREE.LatheGeometry {
  const { r, h, bevel: b } = BODY.head;
  const s = BODY.headStud;
  const pts = [
    [0, 0], [r - b, 0], [r - b * 0.3, b * 0.12], [r - b * 0.06, b * 0.45], [r, b], [r, h - b], [r - b * 0.06, h - b * 0.45], [r - b * 0.3, h - b * 0.12], [r - b, h],
    [s.r, h], [s.r, h + s.h - 0.5], [s.r - 0.5, h + s.h], [s.hollowR, h + s.h], [s.hollowR, h + s.h - 2], [0, h + s.h - 2],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  return new THREE.LatheGeometry(pts, 56);
}

function torsoShapes() {
  const T = BODY.torso;
  const hb = T.wBottom / 2, ht = T.wTop / 2, hn = T.wNeck / 2;
  const outline = [[-hb, 0], [hb, 0], [hb, 3], [ht, T.h - 2], [hn, T.h], [-hn, T.h], [-ht, T.h - 2], [-hb, 3]] as const;
  const shape = (inset: number) => {
    const s = new THREE.Shape();
    outline.forEach(([x, y], i) => {
      const px = x - Math.sign(x) * inset, py = y === 0 ? inset : y === T.h ? y - inset : y;
      if (i) s.lineTo(px, py);
      else s.moveTo(px, py);
    });
    s.closePath();
    return s;
  };
  const body = new THREE.ExtrudeGeometry(shape(T.bevel), { depth: T.d - T.bevel * 2, bevelEnabled: true, bevelThickness: T.bevel, bevelSize: T.bevel, bevelSegments: 3, curveSegments: 1 });
  body.translate(0, 0, -(T.d - T.bevel * 2) / 2);
  const decal = new THREE.ShapeGeometry(shape(0.2));
  const uv = decal.attributes.uv as THREE.BufferAttribute;
  const pos = decal.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (pos.getX(i) + hb) / T.wBottom, pos.getY(i) / T.h); // la estampa cubre el trapecio exacto
  return { body, decal };
}

const GEO = { head: null as THREE.LatheGeometry | null, torso: null as ReturnType<typeof torsoShapes> | null };
const headGeo = () => (GEO.head ??= headGeometry());
const torsoGeo = () => (GEO.torso ??= torsoShapes());

// --- piezas ----------------------------------------------------------------------------------
type V3 = [number, number, number];

function Part({ color, pos, rot, children }: { color: string; pos?: V3; rot?: V3; children: React.ReactNode }) {
  return <mesh position={pos} rotation={rot} castShadow receiveShadow material={plastic(color)}>{children}</mesh>;
}

function Cyl({ r, h, color, pos, rot, seg = 28 }: { r: number; h: number; color: string; pos?: V3; rot?: V3; seg?: number }) {
  return <Part color={color} pos={pos} rot={rot}><cylinderGeometry args={[r, r, h, seg]} /></Part>;
}

function Block({ w, h, d, color, pos, bevel = 1.2 }: { w: number; h: number; d: number; color: string; pos?: V3; bevel?: number }) {
  return (
    <RoundedBox args={[w, h, d]} radius={bevel} smoothness={3} position={pos} castShadow receiveShadow material={plastic(color)} />
  );
}

/** Mano en pinza (C), con muñeca; abierta hacia delante. */
function Hand({ color }: { color: string }) {
  const H = BODY.hand;
  return (
    <group position={[0, -BODY.arm.below, 0]}>
      <Cyl r={H.r * 0.7} h={H.wrist} color={color} pos={[0, -H.wrist / 2, 0]} seg={16} />
      <group position={[0, -H.wrist - H.tube, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <mesh rotation={[0, 0, Math.PI / 2 - 1.775 * Math.PI]} castShadow material={plastic(color)}>
          <torusGeometry args={[H.r, H.tube, 12, 24, H.arc]} />
        </mesh>
      </group>
    </group>
  );
}

function Cone({ r, h, color, pos, rot, seg = 4 }: { r: number; h: number; color: string; pos: V3; rot?: V3; seg?: number }) {
  return <Part color={color} pos={pos} rot={rot}><coneGeometry args={[r, h, seg]} /></Part>;
}

/** Banda de pelo/capucha: lathe parcial que deja libre la cara (o una mitad, para el pelo partido). */
function HairCap({ color, lift = 0, phiStart = 0.75, phiLength = Math.PI * 2 - 1.5, top = true, topStart = 0, topLength = Math.PI * 2 }: { color: string; lift?: number; phiStart?: number; phiLength?: number; top?: boolean; topStart?: number; topLength?: number }) {
  const geo = useMemo(() => {
    const pts = [[13.1, 10.5], [13.3, 13], [13.2, 17], [12.6, 20.2], [10.5, 22.4], [6.5, 24], [0, 24.6]].map(([x, y]) => new THREE.Vector2(x, y + lift));
    return new THREE.LatheGeometry(pts, 40, phiStart, phiLength);
  }, [lift, phiStart, phiLength]);
  const cap = useMemo(() => new THREE.LatheGeometry([[13.0, 18.4], [12.6, 20.2], [10.5, 22.4], [6.5, 24], [0, 24.6]].map(([x, y]) => new THREE.Vector2(x, y + lift)), 40, topStart, topLength), [lift, topStart, topLength]);
  return (
    <>
      <mesh geometry={geo} castShadow material={plastic(color)} />
      {top && <mesh geometry={cap} castShadow material={plastic(color)} />}
    </>
  );
}

function HeadAccessory({ a }: { a: Accessory }) {
  const H = BODY.head.h;
  const R = BODY.head.r;
  switch (a.t) {
    case "ears": {
      const tall = a.kind === "bat" ? 12 : 8;
      const w = a.kind === "bat" ? 4.6 : 5;
      return <>{[-1, 1].map((s) => <Cone key={s} r={w} h={tall} color={a.color} pos={[s * 7.6, H + tall / 2 - 1, -0.5]} rot={[0, Math.PI / 4, -s * 0.14]} />)}</>;
    }
    case "hair":
      if (a.style === "joker")
        return (
          <>
            <HairCap color={a.a} />
            {[-8, -4.5, -1.5, 1.5, 4.5, 8].map((x, i) => <Cone key={i} r={2.6} h={13 - Math.abs(x) * 0.35} color={a.a} pos={[x, H + 7, -2 - Math.abs(x) * 0.4]} rot={[-0.55, 0, -x * 0.07]} seg={6} />)}
          </>
        );
      if (a.style === "split") // Dos Caras: mitad peinada en negro, mitad blanca y de punta (lado quemado)
        return (
          <>
            <HairCap color={a.a} phiStart={Math.PI} phiLength={Math.PI - 0.75} topStart={Math.PI} topLength={Math.PI} />
            <HairCap color={a.b ?? a.a} phiStart={0.75} phiLength={Math.PI - 0.75} topStart={0} topLength={Math.PI} />
            {[3, 7, 10.5].map((x, i) => <Cone key={i} r={2.4} h={9 - i} color={a.b ?? a.a} pos={[x, H + 6.2, -1.5 - i]} rot={[-0.35, 0, -0.25 - i * 0.2]} seg={6} />)}
          </>
        );
      if (a.style === "nightwing")
        return (
          <>
            <HairCap color={a.a} />
            <Cone r={3.4} h={8} color={a.a} pos={[3, H + 6.5, 6]} rot={[0.9, 0, -0.5]} seg={6} />
          </>
        );
      return (
        <>
          <HairCap color={PLASTIC.blond} />
          {[-1, 1].map((s) => (
            <group key={s} position={[s * 15, H - 3.5, -1]}>
              <mesh castShadow material={plastic(s < 0 ? a.a : a.b ?? a.a)}><sphereGeometry args={[4.8, 20, 16]} /></mesh>
              <Cone r={4.2} h={11} color={s < 0 ? a.a : a.b ?? a.a} pos={[s * 3.5, -8, 0]} rot={[0, Math.PI / 4, s * 0.45]} seg={8} />
            </group>
          ))}
        </>
      );
    case "hat": {
      const crown = a.style === "top" ? 17 : 8;
      return (
        <group position={[0, H, 0]}>
          <Cyl r={16.5} h={1.8} color={a.color} pos={[0, 0.9, 0]} seg={40} />
          {a.style === "top" ? <Cyl r={10.4} h={crown} color={a.color} pos={[0, crown / 2, 0]} seg={36} /> : (
            <mesh position={[0, 0.9, 0]} scale={[1, 0.78, 1]} castShadow material={plastic(a.color)}><sphereGeometry args={[11.2, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2]} /></mesh>
          )}
          <Cyl r={a.style === "top" ? 10.6 : 11.3} h={2.6} color={a.band} pos={[0, 3.4, 0]} seg={36} />
        </group>
      );
    }
    case "jester":
      return (
        <>
          <HairCap color={a.a} phiStart={Math.PI} phiLength={Math.PI - 0.75} topStart={Math.PI} topLength={Math.PI} />
          <HairCap color={a.b} phiStart={0.75} phiLength={Math.PI - 0.75} topStart={0} topLength={Math.PI} />
          {[-1, 1].map((sd) => (
            <group key={sd}>
              <Cone r={4.4} h={17} color={sd < 0 ? a.a : a.b} pos={[sd * 9.5, H + 10, -1]} rot={[0, Math.PI / 4, -sd * 0.95]} seg={8} />
              <mesh position={[sd * 17, H + 16.5, -1]} castShadow material={plastic(PLASTIC.white)}><sphereGeometry args={[3, 14, 10]} /></mesh>
            </group>
          ))}
        </>
      );
    case "monocle":
      return <mesh position={[4.6, H * 0.58, R + 0.2]} material={plastic("#C9A227")}><torusGeometry args={[3, 0.45, 8, 24]} /></mesh>;
    case "baneMask":
      return <BaneMask mask={a.mask} hose={a.hose} />;
    default:
      return null;
  }
}

/** Máscara de luchador de Bane: placa respiradora y mangueras verdes que rodean la cabeza hasta la nuca. */
function BaneMask({ mask, hose }: { mask: string; hose: string }) {
  const R = BODY.head.r;
  const tubes = useMemo(() => [-1, 1].map((sd) => new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(sd * 7.2, 5.5, R + 1.4), new THREE.Vector3(sd * 12.6, 8.5, R - 3), new THREE.Vector3(sd * 16.5, 16, -2),
    new THREE.Vector3(sd * 16, 27, -8), new THREE.Vector3(sd * 10, 35, -6), new THREE.Vector3(sd * 5, 30, -2),
  ]), 36, 1.5, 8)), [R]);
  return (
    <group>
      <Block w={15} h={9} d={5} color={PLASTIC.grey} pos={[0, 5.2, R + 0.9]} bevel={1.2} />
      {[-4.5, -1.5, 1.5, 4.5].map((x) => <Block key={x} w={0.9} h={6.5} d={0.8} color={PLASTIC.black} pos={[x, 5.2, R + 3.6]} bevel={0.2} />)}
      <Block w={11} h={2} d={4} color={mask} pos={[0, 14, R - 0.6]} bevel={0.6} />
      {tubes.map((g, i) => <mesh key={i} geometry={g} castShadow material={plastic(hose)} />)}
    </group>
  );
}

/** Objetos que sostienen las figuras en la mano (origen = centro de la pinza; eje vertical). */
const HELD_SCALE = { mallet: 1.55, cane: 1.4, whip: 1.45, coin: 1.35, teeth: 1.35, batarang: 1.6, escrima: 1.3, umbrella: 1.15 } as const;

function HeldItem({ item }: { item: keyof typeof HELD_SCALE }) {
  return <group scale={HELD_SCALE[item]}><HeldItemShape item={item} /></group>;
}

function HeldItemShape({ item }: { item: keyof typeof HELD_SCALE }) {
  const whip = useMemo(() => new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, -6, 0), new THREE.Vector3(0, 12, 1), new THREE.Vector3(3, 26, 6), new THREE.Vector3(9, 38, 8), new THREE.Vector3(14, 50, 3), new THREE.Vector3(9, 60, -5),
  ]), 40, 1.1, 8), []);
  const bat = useMemo(() => {
    const sh = new THREE.Shape();
    [[-11, 2], [-6, 7], [-2, 4], [0, 8], [2, 4], [6, 7], [11, 2], [7, 0], [3, -3], [0, -9], [-3, -3], [-7, 0]].forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y)));
    sh.closePath();
    return new THREE.ExtrudeGeometry(sh, { depth: 1.4, bevelEnabled: false });
  }, []);
  useEffect(() => () => { whip.dispose(); bat.dispose(); }, [whip, bat]);
  switch (item) {
    case "mallet":
      return (
        <group>
          <Cyl r={1.5} h={56} color="#6b4a2a" pos={[0, 12, 0]} seg={10} />
          <Cyl r={7.6} h={26} color="#8a4b2a" pos={[0, 42, 0]} rot={[0, 0, Math.PI / 2]} seg={24} />
          {[-11.5, 11.5].map((x) => <Cyl key={x} r={8} h={3} color={PLASTIC.red} pos={[x, 42, 0]} rot={[0, 0, Math.PI / 2]} seg={24} />)}
        </group>
      );
    case "cane":
      return (
        <group>
          <Cyl r={1.2} h={50} color="#D4A017" pos={[0, 8, 0]} seg={10} />
          <mesh position={[0, 41, 0]} rotation={[0, 0, -0.6]} castShadow material={plastic("#D4A017")}><torusGeometry args={[5.6, 1.3, 8, 22, Math.PI * 1.55]} /></mesh>
          <mesh position={[0, 27, 0]} castShadow material={plastic("#D4A017")}><sphereGeometry args={[2.1, 12, 10]} /></mesh>
        </group>
      );
    case "whip":
      return <mesh geometry={whip} castShadow material={plastic(PLASTIC.black)} />;
    case "coin":
      return (
        <mesh position={[0, 3, 7]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[6.4, 6.4, 1.4, 36]} />
          <meshStandardMaterial color="#d7dbe0" metalness={0.85} roughness={0.28} />
        </mesh>
      );
    case "teeth":
      return (
        <group position={[0, 8, 5]}>
          <Block w={15} h={4} d={8} color={PLASTIC.red} pos={[0, 5, 0]} bevel={1.4} />
          <Block w={15} h={4} d={8} color={PLASTIC.red} pos={[0, -2, 0]} bevel={1.4} />
          {[-5.5, -2.8, 0, 2.8, 5.5].map((x) => <Block key={x} w={2.2} h={3.2} d={2} color={PLASTIC.white} pos={[x, 2.4, 3.6]} bevel={0.5} />)}
          {[-5.5, -2.8, 0, 2.8, 5.5].map((x) => <Block key={`b${x}`} w={2.2} h={3.2} d={2} color={PLASTIC.white} pos={[x, 0.6, 3.6]} bevel={0.5} />)}
        </group>
      );
    case "batarang":
      return <mesh geometry={bat} position={[0, 8, 2]} rotation={[-0.35, 0, 0]} castShadow material={plastic(PLASTIC.black)} />;
    case "escrima":
      return (
        <group rotation={[0.55, 0, 0]}>
          <Cyl r={1.4} h={30} color={PLASTIC.black} pos={[0, 10, 0]} seg={10} />
          <Cyl r={1.7} h={10} color={PLASTIC.blue} pos={[0, -3, 0]} seg={10} />
        </group>
      );
    case "umbrella":
      return (
        <group position={[0, -2, 1]}>
          <Cyl r={0.9} h={56} color={PLASTIC.darkGrey} pos={[0, -2, 0]} seg={8} />
          <mesh position={[0, 24, 0]} rotation={[Math.PI, 0, 0]} castShadow material={plastic(PLASTIC.black)}><coneGeometry args={[5, 28, 14]} /></mesh>
          <mesh position={[2.8, 38, 0]} rotation={[0, 0, Math.PI]} material={plastic(PLASTIC.darkGrey)}><torusGeometry args={[2.8, 0.7, 8, 16, Math.PI]} /></mesh>
        </group>
      );
  }
}

/** Estampado fino (transparente) sobre una cara plana: piernas, espalda… */
function Decal({ ops, w, h, pos, rotY = 0 }: { ops: Parameters<typeof drawOps>[1]; w: number; h: number; pos: V3; rotY?: number }) {
  const tex = useMemo(() => printTexture(ops), [ops]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <mesh position={pos} rotation={[0, rotY, 0]}>
      <planeGeometry args={[w, h]} />
      <meshPhysicalMaterial map={tex} transparent alphaTest={0.02} {...MATERIAL} />
    </mesh>
  );
}

function BackPrint({ ops, geometry }: { ops: Parameters<typeof drawOps>[1]; geometry: THREE.BufferGeometry }) {
  const tex = useMemo(() => printTexture(ops), [ops]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <mesh geometry={geometry} position={[0, 0, -BODY.torso.d / 2 - 0.04]} rotation={[0, Math.PI, 0]} scale={[-1, 1, 1]}>
      <meshPhysicalMaterial map={tex} side={THREE.DoubleSide} {...MATERIAL} />
    </mesh>
  );
}

function Torso({ v }: { v: Variant }) {
  const T = BODY.torso;
  const tex = useMemo(() => printTexture(v.torso), [v]);
  useEffect(() => () => tex.dispose(), [tex]);
  const g = torsoGeo();
  return (
    <group position={[0, HIPS_TOP_Y - HIPS_TOP_Y, 0]}>
      <mesh geometry={g.body} castShadow receiveShadow material={plastic(v.torsoColor)} />
      <mesh geometry={g.decal} position={[0, 0, T.d / 2 + 0.04]}>
        <meshPhysicalMaterial map={tex} {...MATERIAL} />
      </mesh>
      {v.torsoBack && <BackPrint ops={v.torsoBack} geometry={g.decal} />}
    </group>
  );
}

function Head({ v, headRef }: { v: Variant; headRef: React.RefObject<THREE.Group | null> }) {
  const R = BODY.head.r;
  const H = BODY.head.h;
  const tex = useMemo(() => printTexture(v.face), [v]);
  useEffect(() => () => tex.dispose(), [tex]);
  const hasHat = v.accessories.some((a) => a.t === "hat");
  const hasHair = v.accessories.some((a) => a.t === "hair");
  return (
    <group ref={headRef} position={[0, HEAD_BASE_Y - HIPS_TOP_Y, 0]}>
      <mesh geometry={headGeo()} castShadow material={plastic(v.head)} visible={!hasHat && !hasHair} />
      {(hasHat || hasHair) && <mesh geometry={headGeo()} castShadow material={plastic(v.head)} />}
      <mesh position={[0, H / 2, 0]}>
        <cylinderGeometry args={[R + 0.08, R + 0.08, H - BODY.head.bevel * 2, 40, 1, true, -0.74, 1.48]} />
        <meshPhysicalMaterial map={tex} transparent alphaTest={0.02} {...MATERIAL} />
      </mesh>
      {v.accessories.map((a, i) => <HeadAccessory key={i} a={a} />)}
    </group>
  );
}

/** Capa de tela: malla segmentada que ondea con el movimiento (se deforma en cada fotograma). */
function Cape({ outer, inner, poseRef }: { outer: string; inner: string; poseRef: React.RefObject<Pose | null> }) {
  const W = 40, Hh = 52, NY = 10;
  const geoOuter = useMemo(() => new THREE.PlaneGeometry(W, Hh, 6, NY), []);
  const geoInner = useMemo(() => new THREE.PlaneGeometry(W, Hh, 6, NY), []);
  useFrame((s) => {
    const sw = poseRef.current?.cape ?? 0.05;
    for (const [g, side] of [[geoOuter, -1], [geoInner, 1]] as const) {
      const p = g.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < p.count; i++) {
        const y = p.getY(i); // 0 en el hombro → -Hh abajo (el plano está centrado: y ∈ [-Hh/2, Hh/2])
        const k = (Hh / 2 - y) / Hh; // 0 arriba, 1 abajo
        const wave = Math.sin(s.clock.elapsedTime * 2.4 + k * 5 + p.getX(i) * 0.08) * 1.6 * k;
        p.setZ(i, side * 0.25 - (sw * 38 + wave) * k * k);
      }
      p.needsUpdate = true;
      g.computeVertexNormals();
    }
  });
  return (
    <group position={[0, SHOULDER_Y - HIPS_TOP_Y + 6, -BODY.torso.d / 2 - 0.6]}>
      <group position={[0, -Hh / 2, 0]}>
        <mesh geometry={geoOuter} rotation={[0, Math.PI, 0]} castShadow><meshStandardMaterial color={outer} roughness={0.75} side={THREE.FrontSide} /></mesh>
        <mesh geometry={geoInner} castShadow><meshStandardMaterial color={inner} roughness={0.75} side={THREE.FrontSide} /></mesh>
      </group>
    </group>
  );
}

export interface AnimSource {
  (): { state: AnimationState; sinceFinish: number };
}

export function Minifig({ variant: v, getAnim, seed = 0 }: { variant: Variant; getAnim: AnimSource; seed?: number }) {
  const root = useRef<THREE.Group>(null);
  const upper = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const cur = useRef<Pose | null>(null);
  const capeSpec = v.accessories.find((a): a is Extract<Accessory, { t: "cape" }> => a.t === "cape");
  const fur = v.accessories.find((a): a is Extract<Accessory, { t: "furCollar" }> => a.t === "furCollar");
  const held = v.accessories.filter((a): a is Extract<Accessory, { t: "held" }> => a.t === "held");
  const flower = v.accessories.find((a): a is Extract<Accessory, { t: "flower" }> => a.t === "flower");

  useFrame((s, dt) => {
    const { state, sinceFinish } = getAnim();
    const target = poseFor(state, s.clock.elapsedTime, seed, sinceFinish);
    const k = 1 - Math.exp(-dt * 9); // suavizado independiente de los fps
    const lerp = (a: number, b: number) => a + (b - a) * k;
    const c = cur.current ?? target;
    const n: Pose = {
      bodyY: lerp(c.bodyY, target.bodyY), bodyYaw: lerp(c.bodyYaw, target.bodyYaw), headYaw: lerp(c.headYaw, target.headYaw),
      headPitch: lerp(c.headPitch, target.headPitch), legL: lerp(c.legL, target.legL), legR: lerp(c.legR, target.legR), cape: lerp(c.cape, target.cape), lean: lerp(c.lean, target.lean),
      armL: { x: lerp(c.armL.x, target.armL.x), spread: lerp(c.armL.spread, target.armL.spread) },
      armR: { x: lerp(c.armR.x, target.armR.x), spread: lerp(c.armR.spread, target.armR.spread) },
    };
    cur.current = n;
    const tilt = BODY.arm.tilt;
    if (root.current) { root.current.position.y = n.bodyY * POSE_Y; root.current.rotation.y = n.bodyYaw; }
    if (upper.current) upper.current.rotation.x = n.lean;
    if (head.current) { head.current.rotation.y = n.headYaw; head.current.rotation.x = n.headPitch; }
    if (armL.current) { armL.current.rotation.x = n.armL.x; armL.current.rotation.z = -(tilt + n.armL.spread); }
    if (armR.current) { armR.current.rotation.x = n.armR.x; armR.current.rotation.z = tilt + n.armR.spread; }
    if (legL.current) legL.current.rotation.x = n.legL;
    if (legR.current) legR.current.rotation.x = n.legR;
  });

  const L = BODY.legs;
  const A = BODY.arm;
  const shoulderY = SHOULDER_Y - HIPS_TOP_Y;
  const arm = (side: -1 | 1, ref: React.RefObject<THREE.Group | null>, color: string) => (
    <group ref={ref} position={[side * A.shoulderX, shoulderY, 0]}>
      <mesh position={[0, 0, 0]} castShadow material={plastic(color)}><sphereGeometry args={[A.r, 20, 14]} /></mesh>
      <Cyl r={A.r} h={A.below} color={color} pos={[0, -A.below / 2, 0]} seg={24} />
      <Hand color={v.hands} />
      {held.filter((h) => h.hand === (side === -1 ? "l" : "r")).map((h) => (
        <group key={h.item} position={[0, -A.below - BODY.hand.wrist - BODY.hand.tube, 0]}><HeldItem item={h.item} /></group>
      ))}
    </group>
  );

  return (
    <group scale={LDU * (v.scale ?? 1)}>
      <group ref={root}>
        <group ref={legL} position={[-L.x, LEG_TOP_Y, 0]}>
          <Block w={L.w} h={L.h} d={L.d} color={v.legs.l} pos={[0, -L.h / 2, 0]} bevel={L.bevel} />
          {v.legsPrint?.l && <Decal ops={v.legsPrint.l} w={L.w - 0.6} h={L.h - 0.6} pos={[0, -L.h / 2, L.d / 2 + 0.05]} />}
        </group>
        <group ref={legR} position={[L.x, LEG_TOP_Y, 0]}>
          <Block w={L.w} h={L.h} d={L.d} color={v.legs.r} pos={[0, -L.h / 2, 0]} bevel={L.bevel} />
          {v.legsPrint?.r && <Decal ops={v.legsPrint.r} w={L.w - 0.6} h={L.h - 0.6} pos={[0, -L.h / 2, L.d / 2 + 0.05]} />}
        </group>
        <Block w={BODY.hips.w} h={BODY.hips.h} d={BODY.hips.d} color={v.hips} pos={[0, LEG_TOP_Y + BODY.hips.h / 2, 0]} bevel={BODY.hips.bevel} />
        {/* tronco, brazos y cabeza: pivotan juntos en la cadera */}
        <group ref={upper} position={[0, HIPS_TOP_Y, 0]}>
          <Torso v={v} />
          {arm(-1, armL, v.arms.l)}
          {arm(1, armR, v.arms.r)}
          <Head v={v} headRef={head} />
          {fur && <mesh position={[0, BODY.torso.h - 1.2, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[1.05, 0.88, 0.7]} castShadow material={plastic(fur.color)}><torusGeometry args={[11.2, 3.8, 10, 28]} /></mesh>}
          {flower && <mesh position={[8, BODY.torso.h - 14, BODY.torso.d / 2 + 1.2]} material={plastic(flower.color)}><sphereGeometry args={[2.4, 14, 10]} /></mesh>}
          {capeSpec && <Cape outer={capeSpec.outer} inner={capeSpec.inner} poseRef={cur} />}
        </group>
      </group>
    </group>
  );
}
