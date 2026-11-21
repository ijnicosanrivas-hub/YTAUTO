import { useEffect, useState } from "react";
import { elapsed, statusLabel } from "../format";
import type { Action } from "../minifig/hub";
import type { Station } from "../minifig/hub";
import type { AgentState, Persona } from "../types";
import { Badge, Progress } from "./ui";

export interface PipelinePhase { id: string; number: number; title: string; agent: string | null }

const STATE_NOTE: Record<string, string> = {
  idle: "En su puesto, esperando la siguiente tarea.",
  running: "Trabajando ahora mismo.",
  waiting: "Espera tu decisión para continuar.",
  error: "Se ha producido un error; revisa el motivo y reintenta.",
};

const time = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

/** Expediente del agente seleccionado: estado real, tarea actual, estadísticas y últimas acciones. */
export function AgentPanel({ agent, persona, station, phases, actions, quote, onClose, onOverview }: {
  agent: AgentState; persona?: Persona; station?: Station; phases: PipelinePhase[]; actions: Action[]; quote?: string;
  onClose: () => void; onOverview: () => void;
}) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (agent.status !== "running") return;
    const t = setInterval(() => tick((x) => x + 1), 1000); // reloj del tiempo en ejecución
    return () => clearInterval(t);
  }, [agent.status]);
  const mine = phases.filter((p) => p.agent === agent.name);
  const current = phases.find((p) => p.id === agent.phase);
  return (
    <aside className="agent-panel" aria-label={`Expediente de ${persona?.character ?? agent.title}`}>
      <header>
        <span className="glyph">{persona?.glyph ?? "●"}</span>
        <div className="who">
          <b style={persona ? { color: persona.color } : undefined}>{persona?.character ?? agent.title}</b>
          <span className="muted">{agent.title}{persona ? ` · ${persona.epithet}` : ""}</span>
        </div>
        <button className="close" onClick={onClose} aria-label="Cerrar expediente">✕</button>
      </header>

      <div className="row" style={{ gap: 8 }}>
        <Badge status={agent.status} />
        <span className="muted">{agent.uses_claude ? "usa Claude" : "sin Claude (determinista/medios)"}</span>
      </div>
      <p className="note">{STATE_NOTE[agent.status] ?? ""}{quote ? <span className="quote"> «{quote}»</span> : null}</p>

      {station && (
        <section>
          <h3>Instalación</h3>
          <b>{station.name}</b>
          <p className="muted">{station.blurb}</p>
        </section>
      )}

      <section>
        <h3>Ahora</h3>
        {agent.status === "running" ? (
          <>
            <p>{agent.task ?? "Trabajando"}{current ? <span className="muted"> · fase {current.number}: {current.title}</span> : null}</p>
            <Progress value={agent.progress} />
            <p className="mono">⏱ {elapsed(agent.started_at)}{agent.project_id ? <> · <a href={`#/projects/${agent.project_id}`}>ver proyecto</a></> : null}</p>
          </>
        ) : (
          <p className="muted">{statusLabel(agent.status)}{agent.project_id ? <> · último proyecto: <a href={`#/projects/${agent.project_id}`}>abrir</a></> : null}</p>
        )}
        {agent.last_error && agent.status !== "running" && <p className="errline">✖ {agent.last_error}</p>}
      </section>

      <section>
        <h3>Estadísticas</h3>
        <div className="stats">
          <div><b>{agent.runs}</b><span>ejecuciones</span></div>
          <div><b>{agent.errors}</b><span>errores</span></div>
          <div><b>{agent.llm_calls}</b><span>llamadas a Claude</span></div>
          <div><b>{agent.last_duration_s != null ? `${agent.last_duration_s}s` : "—"}</b><span>última duración</span></div>
        </div>
        {agent.last_result && <p>✔ {agent.last_result}</p>}
      </section>

      <section>
        <h3>Fases que gestiona</h3>
        {mine.length ? <ul className="phases">{mine.map((p) => <li key={p.id}><span className="mono">{p.number}</span> {p.title}</li>)}</ul> : <p className="muted">—</p>}
      </section>

      <section>
        <h3>Últimas acciones</h3>
        {actions.length ? (
          <ul className="actions">
            {actions.map((a, i) => <li key={`${a.at}-${i}`}><span className="mono">{time(a.at)}</span> {a.text}</li>)}
          </ul>
        ) : <p className="muted">Aún no ha hecho nada en esta sesión.</p>}
      </section>

      <footer className="row">
        <button className="btn primary" onClick={onOverview}>Vista general</button>
        {agent.project_id && <a className="btn" href={`#/projects/${agent.project_id}`}>Ver proyecto</a>}
      </footer>
    </aside>
  );
}
