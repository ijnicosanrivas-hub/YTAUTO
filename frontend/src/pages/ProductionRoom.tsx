import { Environment, Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { PageHead, useApi } from "../components/ui";
import { AGENT_COLOR, elapsed, statusLabel } from "../format";
import { useLive } from "../store";
import { bodyColor, displayName, personaFor, quoteFor } from "../theme";
import { Batcave, FLOOR_Y, PLATE_H, Plate, StudioLights } from "../minifig/Batcave";
import { Minifig } from "../minifig/Minifig";
import { animationState } from "../minifig/pose";
import { FIGURE_HEIGHT, FIGURE_SCALE } from "../minifig/styleBible";
import { VARIANTS } from "../minifig/variants";
import type { AgentState, Link, Theme } from "../types";

const FEET_Y = FLOOR_Y + PLATE_H;
const CHEST_Y = FEET_Y + 0.7 * FIGURE_SCALE; // las conexiones y etiquetas se anclan a esta altura

const RING_ORDER = ["director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];
const RADIUS = 5;
const ACTIVE_MS = 2500; // una conexión se considera activa si hubo un evento real hace menos de esto

export function nodePositions(): Record<string, [number, number, number]> {
  const pos: Record<string, [number, number, number]> = { chief: [0, 0, 0] };
  RING_ORDER.forEach((name, i) => {
    const a = (i / RING_ORDER.length) * Math.PI * 2 - Math.PI / 2;
    pos[name] = [Math.cos(a) * RADIUS, Math.sin(a * 2) * 0.35, Math.sin(a) * RADIUS];
  });
  return pos;
}

/** Una conexión está activa solo si alguno de sus extremos trabaja o emitió un evento muy reciente. */
export function linkActive(link: Link, agents: Record<string, AgentState>, last: Record<string, number>, now: number): boolean {
  const recent = (n: string) => now - (last[n] ?? 0) < ACTIVE_MS;
  if (link.kind === "control") return agents[link.target]?.status === "running" || recent(link.target);
  return (agents[link.target]?.status === "running" && recent(link.source)) || (recent(link.source) && recent(link.target));
}

type Overlay = React.RefObject<HTMLDivElement | null>;

function Node({ agent, position, central, overlay, theme, figure, receiving, seed }: { agent: AgentState; position: [number, number, number]; central: boolean; overlay: Overlay; theme: Theme; figure: boolean; receiving: boolean; seed: number }) {
  const mesh = useRef<THREE.Mesh>(null);
  const statusColor = AGENT_COLOR[agent.status] ?? "#5b6b8c";
  const color = bodyColor(theme, agent);
  const persona = personaFor(theme, agent.name);
  const quote = quoteFor(theme, agent);
  const [, force] = useState(0);
  useEffect(() => {
    if (agent.status !== "running") return;
    const t = setInterval(() => force((x) => x + 1), 1000); // reloj del tiempo de ejecución
    return () => clearInterval(t);
  }, [agent.status]);
  useFrame((state) => {
    if (!mesh.current) return;
    mesh.current.rotation.y += 0.004;
    // Solo pulsa si el agente está realmente en ejecución
    const s = agent.status === "running" ? 1 + Math.sin(state.clock.elapsedTime * 4) * 0.08 : 1;
    mesh.current.scale.setScalar(s);
  });
  const size = central ? 0.9 : 0.55;
  const variant = figure ? VARIANTS[agent.name] : undefined;
  // La animación se calcula en cada fotograma a partir del estado REAL (sin re-renderizar React)
  const live = useRef({ agent, receiving });
  live.current = { agent, receiving };
  const getAnim = useRef(() => {
    const { agent: a, receiving: r } = live.current;
    return animationState({ status: a.status, finishedAt: a.finished_at, now: Date.now(), receiving: r });
  }).current;
  return (
    <group position={position}>
      {variant ? (
        <>
          <group position={[0, FEET_Y - position[1], 0]} scale={FIGURE_SCALE}>
            <Minifig variant={variant} getAnim={getAnim} seed={seed} />
          </group>
          <Plate position={[0, FLOOR_Y - position[1], 0]} color={color} big={central} />
          {/* Anillo de ESTADO en el borde de la placa; el color del personaje va en la figura y la placa */}
          <mesh position={[0, FEET_Y - position[1] + 0.04, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[central ? 1.2 : 0.92, 0.035, 8, 56]} />
            <meshBasicMaterial color={statusColor} />
          </mesh>
        </>
      ) : (
      <>
      <mesh ref={mesh}>
        <icosahedronGeometry args={[size, 1]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={agent.status === "running" ? 0.9 : 0.25} wireframe={!central} />
      </mesh>
      <mesh>
        <sphereGeometry args={[size * 0.55, 24, 24]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} transparent opacity={0.85} />
      </mesh>
      {/* Anillo con el color del ESTADO real: el cuerpo lleva el color del personaje */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[size * 1.25, 0.04, 8, 48]} />
        <meshBasicMaterial color={statusColor} />
      </mesh>
      </>
      )}
      {/* Las etiquetas van a una capa propia (portal): evita que React y drei compitan por los mismos nodos DOM al salir */}
      <Html position={[0, variant ? FEET_Y - position[1] + FIGURE_HEIGHT * FIGURE_SCALE + (central ? 1.15 : 1.0) : size + 0.35, 0]} center distanceFactor={11} zIndexRange={[10, 0]} portal={overlay as React.RefObject<HTMLElement>}>
        <div className="node-card">
          {persona && <span>{persona.glyph} </span>}<b style={persona ? { color } : undefined}>{displayName(theme, agent)}</b>{persona && <span className="muted"> · {agent.title}</span>} <span style={{ color: statusColor }}>● {statusLabel(agent.status)}</span>
          {quote && <div className="quote">«{quote}»</div>}
          {agent.status === "running" && (
            <>
              <div className="task">{agent.task}</div>
              <div className="progress" style={{ marginTop: 4 }}>
                <div style={{ width: `${Math.round((agent.progress ?? 0) * 100)}%` }} />
              </div>
              <div style={{ marginTop: 3 }}>⏱ {elapsed(agent.started_at)}</div>
            </>
          )}
          {agent.status !== "running" && agent.last_result && <div className="task">✔ {agent.last_result}</div>}
          {agent.status !== "running" && agent.last_duration_s != null && <div className="task">⏱ {agent.last_duration_s}s · {agent.runs} ejecuciones</div>}
          {agent.last_error && agent.status === "error" && <div className="errline">✖ {agent.last_error}</div>}
        </div>
      </Html>
    </group>
  );
}

function Pulse({ from, to }: { from: THREE.Vector3; to: THREE.Vector3 }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ref.current) return;
    const t = (state.clock.elapsedTime * 0.8) % 1;
    ref.current.position.lerpVectors(from, to, t);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.09, 12, 12]} />
      <meshBasicMaterial color="#22d3ee" />
    </mesh>
  );
}

function Scene({ agents, links, overlay, theme }: { agents: Record<string, AgentState>; links: Link[]; overlay: Overlay; theme: Theme }) {
  const last = useLive((s) => s.lastActivity);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const figure = theme.id !== "classic";
  // Con figuras, todas las posiciones (nodos y conexiones) se anclan a la altura del pecho de la minifigura
  const pos = useMemo(() => {
    const base = nodePositions();
    return figure ? Object.fromEntries(Object.entries(base).map(([n, p]) => [n, [p[0], CHEST_Y, p[2]] as [number, number, number]])) : base;
  }, [figure]);
  // "Recibiendo": una entrega real de otro agente hacia éste está en curso
  const receiving = (name: string) => links.some((l) => l.kind === "flow" && l.target === name && now - (last[l.source] ?? 0) < ACTIVE_MS);
  return (
    <>
      {figure ? (
        <>
          <ambientLight intensity={1.1} />
          <hemisphereLight args={["#bcd4ff", "#1a1d26", 0.8]} />
          <directionalLight position={[6, 14, 9]} intensity={3.0} castShadow shadow-mapSize={[1024, 1024]} shadow-camera-left={-12} shadow-camera-right={12} shadow-camera-top={12} shadow-camera-bottom={-12} shadow-bias={-0.0004} />
          <pointLight position={[0, 4, 0]} intensity={18} color={theme.palette.accent} distance={14} />
          <Environment resolution={128}>
            <StudioLights />
          </Environment>
          <Batcave accent={theme.palette.accent} />
        </>
      ) : (
        <>
          <ambientLight intensity={0.5} />
          <pointLight position={[0, 6, 0]} intensity={40} color="#7dd3fc" />
          <Stars radius={60} depth={30} count={1500} factor={3} fade speed={0.3} />
          <gridHelper args={[30, 30, "#1e2a4a", "#121a30"]} position={[0, -1.6, 0]} />
        </>
      )}
      {links.map((l) => {
        const a = pos[l.source];
        const b = pos[l.target];
        if (!a || !b) return null;
        const active = linkActive(l, agents, last, now);
        return (
          <group key={`${l.source}-${l.target}`}>
            <Line points={[a, b]} color={active ? "#22d3ee" : l.kind === "control" ? "#2a3a63" : "#3b2f63"}
              lineWidth={active ? 2.5 : 1} dashed={l.kind === "flow"} dashSize={0.25} gapSize={0.15} transparent opacity={active ? 1 : 0.6} />
            {active && <Pulse from={new THREE.Vector3(...a)} to={new THREE.Vector3(...b)} />}
          </group>
        );
      })}
      {Object.entries(pos).map(([name, p], i) => agents[name] && (
        <Node key={name} agent={agents[name]} position={p} central={name === "chief"} overlay={overlay} theme={theme}
          figure={figure} receiving={receiving(name)} seed={i * 1.7} />
      ))}
      <OrbitControls enablePan={false} minDistance={4} maxDistance={24} maxPolarAngle={Math.PI / 2.1} />
    </>
  );
}

export default function ProductionRoom() {
  const overlay = useRef<HTMLDivElement>(null);
  const { data } = useApi<{ agents: AgentState[]; links: Link[] }>("/api/agents");
  const live = useLive((s) => s.agents);
  const connected = useLive((s) => s.connected);
  const theme = useLive((s) => s.theme);
  const agents = useMemo(() => {
    const base = Object.fromEntries((data?.agents ?? []).map((a) => [a.name, a]));
    return { ...base, ...live };
  }, [data, live]);
  const running = Object.values(agents).filter((a) => a.status === "running");
  return (
    <>
      <PageHead title={theme.room_title} subtitle={`${theme.room_subtitle}. Nueve agentes y sus conexiones: todo lo que se mueve corresponde a actividad real.`}>
        <span className={`badge ${connected ? "s-completed" : "s-error"}`}>{connected ? "En directo" : "Sin conexión"}</span>
        <span className="badge s-running">{running.length} en ejecución</span>
      </PageHead>
      <div className="panel room">
        <Canvas shadows camera={{ position: [0, 8.5, 14], fov: 48 }} dpr={[1, 2]}>
          <color attach="background" args={[theme.id === "classic" ? "#05070f" : theme.palette.background]} />
          <Scene agents={agents} links={data?.links ?? []} overlay={overlay} theme={theme} />
        </Canvas>
        <div ref={overlay} className="room-overlay" />
        <div className="room-legend">
          {(["idle", "running", "waiting", "error"] as const).map((s) => (
            <span key={s}><span style={{ color: AGENT_COLOR[s] }}>●</span> {statusLabel(s)}</span>
          ))}
          <span>○ anillo = estado · cuerpo = personaje</span>
          <span>── control (jefe → agente)</span>
          <span>- - entrega entre agentes</span>
        </div>
      </div>
    </>
  );
}
