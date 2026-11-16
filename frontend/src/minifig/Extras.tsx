/** Puesto de trabajo de cada personaje y efectos de ladrillos ligados al estado real del agente. */
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Brick, screenTexture } from "./Batcave";
import { BRICK_H, PITCH } from "./bricks";
import { BURST_COUNT, CONFETTI_COLORS, SPARK_COLORS, burstPosition, seedFrom } from "./fx";
import { plastic } from "./Minifig";
import type { AnimSource } from "./Minifig";
import { FIGURE_HEIGHT, LDU, PLASTIC as P } from "./styleBible";

/** Atril de trabajo delante de la figura: su pantalla solo se enciende cuando el agente está en ejecución. */
export function Workstation({ active, tint, seed }: { active: boolean; tint: string; seed: number }) {
  const tex = useMemo(() => screenTexture(seed + 3, tint, "TRABAJANDO"), [seed, tint]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[0, 0, 1.3]}>
      <Brick w={3} d={2} h={1} color={P.darkGrey} pos={[0, 0, 0]} />
      <group position={[0, BRICK_H + 0.05, 0.05]} rotation={[-1.05, 0, 0]}>
        <mesh castShadow material={plastic(P.black)}><boxGeometry args={[2.6 * PITCH, 1.5 * PITCH, 0.28 * PITCH]} /></mesh>
        <mesh position={[0, 0, 0.15 * PITCH]}>
          <planeGeometry args={[2.3 * PITCH, 1.25 * PITCH]} />
          <meshBasicMaterial map={tex} toneMapped={false} color={active ? "#ffffff" : "#2c3a40"} />
        </mesh>
      </group>
    </group>
  );
}

/** Confeti de ladrillos al terminar, chispas al fallar y un «!» flotante cuando espera tu decisión. */
export function FigureFx({ getAnim, finishedAt, seed }: { getAnim: AnimSource; finishedAt: string | null; seed: number }) {
  const pieces = useRef<(THREE.Mesh | null)[]>([]);
  const bang = useRef<THREE.Group>(null);
  const s0 = seedFrom(finishedAt) + seed;
  const headY = (FIGURE_HEIGHT + 6) * LDU;
  useFrame((st) => {
    const { state, sinceFinish } = getAnim();
    const t = st.clock.elapsedTime;
    pieces.current.forEach((m, i) => {
      if (!m) return;
      let show = false;
      if (state === "finish") {
        const [x, y, z] = burstPosition(s0, i, sinceFinish);
        m.position.set(x, headY + y, z);
        show = y > -headY;
        (m.material as THREE.MeshPhysicalMaterial) = plastic(CONFETTI_COLORS[i % CONFETTI_COLORS.length]);
      } else if (state === "error") {
        const ph = (t * 0.9 + i * 0.12) % 1.1;
        const [x, y, z] = burstPosition(s0, i, ph, 1.2, 1.6);
        m.position.set(x * 0.5, headY * 0.8 + y, z * 0.5);
        show = true;
        (m.material as THREE.MeshPhysicalMaterial) = plastic(SPARK_COLORS[i % SPARK_COLORS.length]);
      }
      m.visible = show;
      m.rotation.set(t * 3 + i, t * 2 + i * 2, 0);
    });
    if (bang.current) {
      bang.current.visible = state === "interact";
      bang.current.position.y = headY + 0.55 + Math.sin(t * 4) * 0.06;
      bang.current.rotation.y = t * 1.5;
    }
  });
  return (
    <>
      {Array.from({ length: BURST_COUNT }, (_, i) => (
        <mesh key={i} ref={(m) => { pieces.current[i] = m; }} visible={false} castShadow>
          <boxGeometry args={[0.16, 0.08, 0.08]} />
          <meshPhysicalMaterial color="#fff" />
        </mesh>
      ))}
      <group ref={bang} visible={false}>
        <mesh castShadow material={plastic(P.yellow)} position={[0, 0.17, 0]}><boxGeometry args={[0.17, 0.42, 0.17]} /></mesh>
        <mesh castShadow material={plastic(P.yellow)} position={[0, -0.14, 0]}><boxGeometry args={[0.17, 0.17, 0.17]} /></mesh>
      </group>
    </>
  );
}
