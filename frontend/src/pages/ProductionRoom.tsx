import { Environment, Html, Line, OrbitControls, PerformanceMonitor, Stars } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { PageHead, useApi } from "../components/ui";
import { AGENT_COLOR, elapsed, statusLabel } from "../format";
import { useLive } from "../store";
import { bodyColor, displayName, personaFor, quoteFor } from "../theme";
import { Base, Batcave, FLOOR_Y, PLATE_H, StudioLights, plateRadius } from "../minifig/Batcave";
import { AgentPanel, type PipelinePhase } from "../components/AgentPanel";
import { BatSwarm, Facilities, FloorPads } from "../minifig/Hub";
import { HUB, HUB_SCALE, OVERVIEW, facingYaw, focusShot, recentActions } from "../minifig/hub";
import { FigureFx, Workstation } from "../minifig/Extras";
import { Minifig } from "../minifig/Minifig";
import { SpriteFigure, useFigureTexture } from "../minifig/SpriteFigure";
import { spriteSize, type FigureMeta } from "../minifig/sprites";
import { animationState } from "../minifig/pose";
import { FIGURE_HEIGHT, LDU } from "../minifig/styleBible";
import { VARIANTS } from "../minifig/variants";
import type { AgentState, Link, Theme, YtEvent } from "../types";

/** Calidad gráfica: «alta» (brillo, antialiasing, sombras) o «baja» (equipos modestos). Se degrada sola si los fotogramas caen. */
function initialQuality(): { quality: "high" | "low"; locked: boolean } {
  try {
    const q = new URLSearchParams(location.hash.split("?")[1] ?? "").get("calidad") ?? localStorage.getItem("ytauto.calidad");
    if (q === "alta") return { quality: "high", locked: true };
    if (q === "baja") return { quality: "low", locked: true };
  } catch { /* sin almacenamiento: calidad automática */ }
  return { quality: "high", locked: false };
}

const FEET_Y = FLOOR_Y + PLATE_H;

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
          <group position={[0, FEET_Y - position[1], 0]}>
            <Minifig variant={variant} getAnim={getAnim} seed={seed} />
            <Workstation active={agent.status === "running"} tint={color} seed={seed} />
            <FigureFx getAnim={getAnim} finishedAt={agent.finished_at} seed={seed} />
          </group>
          <Base position={[0, FLOOR_Y - position[1], 0]} color={color} big={central} label={persona?.character ?? agent.title} />
          {/* Anillo de ESTADO en el borde de la placa; el color del personaje va en la figura y la placa */}
          <mesh position={[0, FEET_Y - position[1] + 0.04, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[plateRadius(central) + 0.07, 0.035, 8, 64]} />
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
      <Html position={[0, variant ? FEET_Y - position[1] + FIGURE_HEIGHT * LDU * (variant?.scale ?? 1) + 0.95 : size + 0.35, 0]} center distanceFactor={variant ? 8.5 : 11} zIndexRange={[10, 0]} portal={overlay as React.RefObject<HTMLElement>}>
        <div className={`node-card${variant && agent.status === "idle" ? " compact" : ""}`}>
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
    ref.current.rotation.set(state.clock.elapsedTime * 4, state.clock.elapsedTime * 3, 0); // el paquete de datos es un ladrillo que gira
  });
  return (
    <mesh ref={ref} castShadow>
      <boxGeometry args={[0.2, 0.1, 0.1]} />
      <meshPhysicalMaterial color="#F2CD37" roughness={0.3} clearcoat={0.5} emissive="#F2CD37" emissiveIntensity={0.5} />
    </mesh>
  );
}

/** Posición del pecho de un personaje en el hub (ancla de las conexiones). */
function hubChest(name: string): [number, number, number] {
  const s = HUB[name];
  return [s.x, FLOOR_Y + PLATE_H * HUB_SCALE + 0.62 * FIGURE_HEIGHT * LDU * HUB_SCALE, s.z];
}

/** Personaje del hub: minifigura mirando a Batman (o a su instalación al trabajar), clicable. */
function HubNode({ agent, theme, overlay, selected, onSelect, receiving, seed, figure }: { figure?: FigureMeta; agent: AgentState; theme: Theme; overlay: Overlay; selected: boolean; onSelect: (n: string) => void; receiving: boolean; seed: number }) {
  const s = HUB[agent.name];
  const variant = VARIANTS[agent.name];
  const central = agent.name === "chief";
  const statusColor = AGENT_COLOR[agent.status] ?? "#5b6b8c";
  const color = bodyColor(theme, agent);
  const persona = personaFor(theme, agent.name);
  const [hover, setHover] = useState(false);
  const live = useRef({ agent, receiving });
  live.current = { agent, receiving };
  const getAnim = useRef(() => {
    const { agent: a, receiving: r } = live.current;
    return animationState({ status: a.status, finishedAt: a.finished_at, now: Date.now(), receiving: r });
  }).current;
  useEffect(() => () => { document.body.style.cursor = ""; }, []);
  const sprite = useFigureTexture(agent.name, !!figure);
  if (!s || !variant) return null;
  const top = PLATE_H + (sprite && figure ? spriteSize(figure).height * (variant.scale ?? 1) : FIGURE_HEIGHT * LDU * (variant.scale ?? 1)) + 0.5;
  return (
    <group position={[s.x, FLOOR_Y, s.z]} scale={HUB_SCALE}
      onClick={(e) => { e.stopPropagation(); onSelect(agent.name); }}
      onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
      onPointerOut={() => { setHover(false); document.body.style.cursor = ""; }}>
      <group position={[0, PLATE_H, 0]}>
        {sprite && figure
          ? <SpriteFigure texture={sprite} meta={figure} scale={variant.scale ?? 1} getAnim={getAnim} seed={seed} glowColor={statusColor} />
          : <Minifig variant={variant} getAnim={getAnim} seed={seed} yaw={facingYaw(agent.name)} turnToWork />}
        <FigureFx getAnim={getAnim} finishedAt={agent.finished_at} seed={seed} />
      </group>
      <Base position={[0, 0, 0]} color={color} big={central} label={persona?.character ?? agent.title} />
      {/* anillo de ESTADO real; el aro amarillo exterior marca el personaje seleccionado o bajo el cursor */}
      <mesh position={[0, PLATE_H + 0.04, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[plateRadius(central) + 0.07, 0.035, 8, 64]} />
        <meshBasicMaterial color={statusColor} />
      </mesh>
      {(selected || hover) && (
        <mesh position={[0, PLATE_H + 0.06, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[plateRadius(central) + 0.18, plateRadius(central) + 0.3, 64]} />
          <meshBasicMaterial color={selected ? "#ffd400" : "#ffffff"} toneMapped={false} />
        </mesh>
      )}
      {!selected && (
        <Html position={[0, top, 0]} center distanceFactor={11} zIndexRange={[10, 0]} portal={overlay as React.RefObject<HTMLElement>}>
          <div className={`node-card compact${hover ? " selected" : ""}`}>
            {persona && <span>{persona.glyph} </span>}<b style={{ color }}>{displayName(theme, agent)}</b> <span style={{ color: statusColor }}>● {statusLabel(agent.status)}</span>
          </div>
        </Html>
      )}
    </group>
  );
}

/** Vuela la cámara hasta el personaje seleccionado (o a la vista general); si el usuario orbita, deja de forzarla. */
function CameraRig({ selected, manual }: { selected: string | null; manual: React.MutableRefObject<boolean> }) {
  const camera = useThree((st) => st.camera);
  const controls = useThree((st) => st.controls) as unknown as { target: THREE.Vector3; update: () => void } | null;
  const shot = useMemo(() => (selected ? focusShot(selected, FLOOR_Y + PLATE_H * HUB_SCALE) : OVERVIEW), [selected]);
  const goal = useMemo(() => ({ p: new THREE.Vector3(...shot.position), t: new THREE.Vector3(...shot.target) }), [shot]);
  useFrame((_, dt) => {
    if (manual.current || !controls) return;
    const k = 1 - Math.exp(-dt * 3.4);
    camera.position.lerp(goal.p, k);
    controls.target.lerp(goal.t, k);
    controls.update();
    if (camera.position.distanceTo(goal.p) < 0.04 && controls.target.distanceTo(goal.t) < 0.04) manual.current = true; // llegó: el usuario manda
  });
  return null;
}

function HubScene({ agents, links, overlay, theme, quality, selected, onSelect, manual }: { agents: Record<string, AgentState>; links: Link[]; overlay: Overlay; theme: Theme; quality: "high" | "low"; selected: string | null; onSelect: (n: string | null) => void; manual: React.MutableRefObject<boolean> }) {
  const last = useLive((st) => st.lastActivity);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const receiving = (name: string) => links.some((l) => l.kind === "flow" && l.target === name && now - (last[l.source] ?? 0) < ACTIVE_MS);
  const { data: figures } = useApi<Record<string, FigureMeta>>("/api/figures");
  const colors = useMemo(() => Object.fromEntries(Object.keys(HUB).map((n) => [n, personaFor(theme, n)?.color ?? "#ffffff"])), [theme]);
  return (
    <>
      <ambientLight intensity={1.5} />
      <hemisphereLight args={["#bfe3f0", "#202733", 1.1]} />
      <directionalLight position={[6, 16, 10]} intensity={2.4} castShadow shadow-mapSize={[1024, 1024]} shadow-camera-left={-16} shadow-camera-right={16} shadow-camera-top={16} shadow-camera-bottom={-16} shadow-bias={-0.0004} />
      <Environment resolution={128}>
        <StudioLights />
      </Environment>
      <Batcave accent={theme.palette.accent} />
      <FloorPads />
      <Facilities agents={agents} colors={colors} />
      <BatSwarm />
      {quality === "high" && (
        <EffectComposer multisampling={4}>
          <Bloom intensity={0.6} luminanceThreshold={0.85} mipmapBlur />
          <Vignette offset={0.25} darkness={0.6} />
        </EffectComposer>
      )}
      {links.map((l) => {
        if (!HUB[l.source] || !HUB[l.target]) return null;
        const a = hubChest(l.source), b = hubChest(l.target);
        const active = linkActive(l, agents, last, now);
        return (
          <group key={`${l.source}-${l.target}`}>
            <Line points={[a, b]} color={active ? "#22d3ee" : l.kind === "control" ? "#1d3a4a" : "#2c2a4a"} lineWidth={active ? 2.8 : 1} dashed={l.kind === "flow"} dashSize={0.3} gapSize={0.2} transparent opacity={active ? 1 : 0.5} />
            {active && <Pulse from={new THREE.Vector3(...a)} to={new THREE.Vector3(...b)} />}
          </group>
        );
      })}
      {Object.keys(HUB).map((name, i) => agents[name] && (
        <HubNode key={name} agent={agents[name]} theme={theme} overlay={overlay} selected={selected === name} onSelect={onSelect} receiving={receiving(name)} seed={i * 1.7} figure={figures?.[name]} />
      ))}
      <OrbitControls makeDefault enablePan={false} target={OVERVIEW.target} minDistance={2.5} maxDistance={40} maxPolarAngle={Math.PI / 2.05}
        onStart={() => { manual.current = true; }} />
      <CameraRig selected={selected} manual={manual} />
    </>
  );
}

function ClassicScene({ agents, links, overlay, theme }: { agents: Record<string, AgentState>; links: Link[]; overlay: Overlay; theme: Theme }) {
  const last = useLive((s) => s.lastActivity);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const pos = useMemo(nodePositions, []);
  const receiving = (name: string) => links.some((l) => l.kind === "flow" && l.target === name && now - (last[l.source] ?? 0) < ACTIVE_MS);
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
      {Object.entries(pos).map(([name, p], i) => agents[name] && (
        <Node key={name} agent={agents[name]} position={p} central={name === "chief"} overlay={overlay} theme={theme} figure={false} receiving={receiving(name)} seed={i * 1.7} />
      ))}
      <OrbitControls enablePan={false} target={[0, 1.2, -3]} minDistance={4} maxDistance={32} maxPolarAngle={Math.PI / 2.1} />
    </>
  );
}

export default function ProductionRoom() {
  const overlay = useRef<HTMLDivElement>(null);
  const initial = useMemo(initialQuality, []);
  const [quality, setQuality] = useState<"high" | "low">(initial.quality);
  const { data } = useApi<{ agents: AgentState[]; links: Link[]; pipeline: PipelinePhase[] }>("/api/agents");
  const { data: events } = useApi<YtEvent[]>("/api/events?limit=500", { live: true });
  const live = useLive((st) => st.agents);
  const connected = useLive((st) => st.connected);
  const theme = useLive((st) => st.theme);
  const hub = theme.id !== "classic";
  const manual = useRef(false);
  const [selected, setSelected] = useState<string | null>(() => {
    try { const a = new URLSearchParams(location.hash.split("?")[1] ?? "").get("agente"); return a && HUB[a] ? a : null; } catch { return null; }
  });
  const select = (n: string | null) => { manual.current = false; setSelected(n); };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") select(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const agents = useMemo(() => {
    const base = Object.fromEntries((data?.agents ?? []).map((a) => [a.name, a]));
    return { ...base, ...live };
  }, [data, live]);
  const running = Object.values(agents).filter((a) => a.status === "running");
  const phaseAgent = useMemo(() => Object.fromEntries((data?.pipeline ?? []).map((p) => [p.id, p.agent])), [data]);
  const sel = selected ? agents[selected] : undefined;
  const liveEvents = useLive((st) => st.events);
  const actions = useMemo(() => {
    if (!selected) return [];
    const merged = [...liveEvents, ...(events ?? [])];
    const seen = new Set<string>();
    return recentActions(merged.filter((e) => { const k = `${e.at}|${e.type}|${e.agent}|${e.phase}`; if (seen.has(k)) return false; seen.add(k); return true; }), selected, phaseAgent);
  }, [selected, liveEvents, events, phaseAgent]);
  return (
    <>
      <PageHead title={theme.room_title} subtitle={`${theme.room_subtitle}. Haz clic en un agente para ver su expediente: todo lo que se mueve corresponde a actividad real.`}>
        <span className={`badge ${connected ? "s-completed" : "s-error"}`}>{connected ? "En directo" : "Sin conexión"}</span>
        <span className="badge s-running">{running.length} en ejecución</span>
        {hub && (
          <button className="btn" title="Calidad gráfica: alta usa brillos, antialiasing y sombras; baja es para equipos modestos" onClick={() => { const q = quality === "high" ? "low" : "high"; setQuality(q); try { localStorage.setItem("ytauto.calidad", q === "high" ? "alta" : "baja"); } catch { /* sin almacenamiento */ } }}>
            Calidad: {quality === "high" ? "alta" : "baja"}
          </button>
        )}
      </PageHead>
      <div className="panel room">
        <Canvas shadows={quality === "high"} dpr={quality === "high" ? [1, 2] : 1} camera={{ position: hub ? OVERVIEW.position : [0, 7, 11], fov: hub ? 46 : 50 }} onPointerMissed={() => hub && select(null)}>
          {!initial.locked && hub && <PerformanceMonitor onDecline={() => setQuality("low")} />}
          <color attach="background" args={[hub ? theme.palette.background : "#05070f"]} />
          {hub ? (
            <HubScene agents={agents} links={data?.links ?? []} overlay={overlay} theme={theme} quality={quality} selected={selected} onSelect={select} manual={manual} />
          ) : (
            <ClassicScene agents={agents} links={data?.links ?? []} overlay={overlay} theme={theme} />
          )}
        </Canvas>
        <div ref={overlay} className="room-overlay" />
        {hub && sel && (
          <AgentPanel agent={sel} persona={personaFor(theme, sel.name)} station={HUB[sel.name]} phases={data?.pipeline ?? []} actions={actions}
            quote={quoteFor(theme, sel)} onClose={() => select(null)} onOverview={() => select(null)} />
        )}
        <div className="room-legend">
          {(["idle", "running", "waiting", "error"] as const).map((s) => (
            <span key={s}><span style={{ color: AGENT_COLOR[s] }}>●</span> {statusLabel(s)}</span>
          ))}
          <span>○ anillo = estado</span>
          {hub && <span>clic en un agente = expediente · Esc = vista general</span>}
        </div>
      </div>
    </>
  );
}
