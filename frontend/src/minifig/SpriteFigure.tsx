import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { getToken } from "../api";
import { DEMO } from "../demo/demo";
import { figureImage } from "../channels";
import { billboardYaw, spriteMotion, spriteSize, type FigureMeta } from "./sprites";
import type { animationState } from "./pose";

type Anim = ReturnType<typeof animationState>;

/** Carga el recorte del personaje; `null` mientras llega o si falla (la sala usa entonces la figura de ladrillos). */
export function useFigureTexture(agent: string, enabled: boolean, profile = "gotham"): THREE.Texture | null {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let dead = false;
    new THREE.TextureLoader().load(DEMO ? `/personajes/${agent}.png` : figureImage(profile, agent, getToken() || null), (t) => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 8;
      t.generateMipmaps = true;
      t.minFilter = THREE.LinearMipmapLinearFilter;
      if (dead) t.dispose(); else setTex(t);
    }, undefined, () => { if (!dead) setTex(null); });
    return () => { dead = true; };
  }, [agent, enabled, profile]);
  useEffect(() => () => tex?.dispose(), [tex]);
  return tex;
}

/** Figura 2D del render, siempre de cara a la cámara, animada con el estado real del agente. */
export function SpriteFigure({ texture, meta, scale = 1, getAnim, seed, glowColor }: {
  texture: THREE.Texture; meta: FigureMeta; scale?: number; getAnim: () => Anim; seed: number; glowColor: string;
}) {
  const size = useMemo(() => spriteSize(meta), [meta]);
  const root = useRef<THREE.Group>(null);
  const body = useRef<THREE.Group>(null);
  const glow = useRef<THREE.MeshBasicMaterial>(null);
  const camera = useThree((s) => s.camera);
  const tmp = useMemo(() => new THREE.Vector3(), []);
  const w = size.width * scale, h = size.height * scale;
  useFrame(({ clock }) => {
    if (!root.current || !body.current) return;
    root.current.getWorldPosition(tmp);
    root.current.rotation.y = billboardYaw([camera.position.x, camera.position.z], [tmp.x, tmp.z]);
    const { state, sinceFinish } = getAnim();
    const m = spriteMotion(state, clock.elapsedTime, seed, sinceFinish);
    body.current.position.set(m.x, m.y, 0);
    body.current.rotation.z = m.rot;
    body.current.scale.set(m.sx, m.sy, 1);
    if (glow.current) glow.current.opacity = 0.35 * m.glow;
  });
  return (
    <group ref={root}>
      {/* pivote en los pies: el cartel se inclina y respira desde la base */}
      <group ref={body}>
        <mesh position={[size.offsetX * scale, h / 2, 0]} castShadow>
          <planeGeometry args={[w, h]} />
          <meshBasicMaterial map={texture} transparent alphaTest={0.08} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0, 0.03, 0.01]} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.9 * scale, 40]} />
          <meshBasicMaterial ref={glow} color={glowColor} transparent opacity={0} depthWrite={false} toneMapped={false} />
        </mesh>
      </group>
    </group>
  );
}
