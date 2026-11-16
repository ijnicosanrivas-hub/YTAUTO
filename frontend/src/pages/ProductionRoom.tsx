import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { PageHead, useApi } from "../components/ui";
import { AGENT_COLOR, elapsed, statusLabel } from "../format";
import { useLive } from "../store";
import { bodyColor, displayName, personaFor, quoteFor } from "../theme";
import type { AgentState, Link, Theme } from "../types";

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

function Node({ agent, position, central, overlay, theme }: { agent: AgentState; position: [number, number, number]; central: boolean; overlay: Overlay; theme: Theme }) {
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
  return (
    <group position={position}>
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
      {/* Las etiquetas van a una capa propia (portal): evita que React y drei compitan por los mismos nodos DOM al salir */}
      <Html position={[0, size + 0.35, 0]} center distanceFactor={11} zIndexRange={[10, 0]} portal={overlay as React.RefObject<HTMLElement>}>
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

/** Ambientación Gotham: horizonte de edificios y señal del Murciélago. Decorativo, sin significado de estado. */
function Gotham({ accent }: { accent: string }) {
  const towers = useMemo(
    () => Array.from({ length: 28 }, (_, i) => {
      const a = (i / 28) * Math.PI * 2;
      const h = 3 + ((i * 7919) % 11) * 0.9; // alturas deterministas
      return { x: Math.cos(a) * 22, z: Math.sin(a) * 22, h, w: 1.4 + (i % 3) * 0.5 };
    }),
    [],
  );
  return (
    <>
      {towers.map((t, i) => (
        <mesh key={i} position={[t.x, -1.6 + t.h / 2, t.z]}>
          <boxGeometry args={[t.w, t.h, t.w]} />
          <meshStandardMaterial color="#0b0d14" emissive="#10131f" emissiveIntensity={0.6} />
        </mesh>
      ))}
      {/* Haz de la señal sobre el jefe */}
      <mesh position={[0, 5, 0]}>
        <coneGeometry args={[2.2, 14, 32, 1, true]} />
        <meshBasicMaterial color={accent} transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </>
  );
}

function Scene({ agents, links, overlay, theme }: { agents: Record<string, AgentState>; links: Link[]; overlay: Overlay; theme: Theme }) {
  const last = useLive((s) => s.lastActivity);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const pos = useMemo(nodePositions, []);
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 6, 0]} intensity={40} color="#7dd3fc" />
      <Stars radius={60} depth={30} count={1500} factor={3} fade speed={0.3} />
      <gridHelper args={[30, 30, "#1e2a4a", "#121a30"]} position={[0, -1.6, 0]} />
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
      {Object.entries(pos).map(([name, p]) => agents[name] && <Node key={name} agent={agents[name]} position={p} central={name === "chief"} overlay={overlay} theme={theme} />)}
      {theme.id !== "classic" && <Gotham accent={theme.palette.accent} />}
      <OrbitControls enablePan={false} minDistance={6} maxDistance={22} maxPolarAngle={Math.PI / 2.1} />
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
        <Canvas camera={{ position: [0, 7, 11], fov: 50 }} dpr={[1, 2]}>
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
