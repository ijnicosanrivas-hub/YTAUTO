import { AGENT_COLOR, describeEvent, eur, shortDate } from "../format";
import { Badge, ErrorBox, PageHead, Progress, useApi } from "../components/ui";
import { useLive } from "../store";
import type { AgentState, ProjectSummary, YtEvent } from "../types";

interface Dash {
  projects: { total: number; by_status: Record<string, number> };
  waiting_approval: { id: string; name: string; gates: string[] }[];
  claude: { calls: number; seconds: number; lanes: Record<string, { paused: boolean; reason: string | null; concurrency: number }> };
  budget: { spent_month_eur: number; monthly_budget_eur: number | null } | null;
  agents: AgentState[];
}

export default function Dashboard() {
  const { data, error } = useApi<Dash>("/api/dashboard", { live: true });
  const { data: projects } = useApi<ProjectSummary[]>("/api/projects", { live: true });
  const liveEvents = useLive((s) => s.events);
  // Historial reciente persistido + eventos que llegan en directo (sin duplicar)
  const { data: recent } = useApi<YtEvent[]>("/api/events?limit=60");
  const seen = new Set(liveEvents.map((e) => e.at + e.type + e.agent));
  const events = [...liveEvents, ...[...(recent ?? [])].reverse().filter((e) => !seen.has(e.at + e.type + e.agent))];
  const liveAgents = useLive((s) => s.agents);
  const agents = Object.keys(liveAgents).length ? Object.values(liveAgents) : (data?.agents ?? []);
  const claudeLane = data?.claude.lanes.claude;

  return (
    <>
      <PageHead title="Dashboard" subtitle="Estado real de la fábrica: proyectos, agentes, Claude y presupuesto">
        <a className="btn primary" href="#/projects">
          + Nuevo vídeo
        </a>
      </PageHead>
      <ErrorBox error={error} />
      {claudeLane?.paused && (
        <div className="alert">
          Carril de Claude en pausa: {claudeLane.reason}. <a href="#/models">Gestionar</a>
        </div>
      )}
      <div className="grid cols-4">
        <div className="panel">
          <h2>Proyectos</h2>
          <div className="kpi">
            {data?.projects.total ?? "—"}
            <small>{data?.projects.by_status.active ?? 0} en curso</small>
          </div>
        </div>
        <div className="panel">
          <h2>Pendientes de aprobación</h2>
          <div className="kpi">{data?.waiting_approval.length ?? "—"}</div>
        </div>
        <div className="panel">
          <h2>Llamadas a Claude</h2>
          <div className="kpi">
            {data?.claude.calls ?? "—"}
            <small>{data ? `${Math.round(data.claude.seconds)} s` : ""}</small>
          </div>
        </div>
        <div className="panel">
          <h2>Gasto externo (mes)</h2>
          <div className="kpi">
            {eur(data?.budget?.spent_month_eur ?? 0)}
            <small>{data?.budget?.monthly_budget_eur != null ? `de ${eur(data.budget.monthly_budget_eur)}` : "sin límite"}</small>
          </div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <div className="panel">
          <h2>Requieren tu decisión</h2>
          {data?.waiting_approval.length ? (
            <table>
              <tbody>
                {data.waiting_approval.map((w) => (
                  <tr key={w.id} className="clickable" onClick={() => (location.hash = `#/projects/${w.id}`)}>
                    <td>{w.name}</td>
                    <td>{w.gates.map((g) => <Badge key={g} status="in_review" label={g} />)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">Nada pendiente</div>
          )}
        </div>
        <div className="panel">
          <h2>Agentes</h2>
          <table>
            <tbody>
              {agents.map((a) => (
                <tr key={a.name}>
                  <td>
                    <span style={{ color: AGENT_COLOR[a.status] }}>●</span> {a.title}
                  </td>
                  <td className="muted" style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {a.status === "running" ? a.task : a.last_result ?? "—"}
                  </td>
                  <td style={{ width: 90 }}>{a.status === "running" && <Progress value={a.progress} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <div className="panel">
          <h2>Producciones recientes</h2>
          {projects?.length ? (
            <table>
              <tbody>
                {projects.slice(0, 8).map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => (location.hash = `#/projects/${p.id}`)}>
                    <td>
                      {p.name}
                      <div className="muted mono">{shortDate(p.created_at)}</div>
                    </td>
                    <td style={{ width: 140 }}>
                      <Progress value={p.progress} />
                    </td>
                    <td>
                      <Badge status={p.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">Aún no hay producciones</div>
          )}
        </div>
        <div className="panel">
          <h2>Actividad en directo</h2>
          <div className="event-log">
            {events.filter((e) => e.type !== "agent.progress").slice(0, 40).map((e, i) => (
              <div key={i}>
                <span className="muted">{new Date(e.at).toLocaleTimeString("es-ES")}</span>
                <span>{e.agent ?? e.phase ?? "sistema"}</span>
                <span>{describeEvent(e.type, e.data)}</span>
              </div>
            ))}
            {!events.length && <div className="empty">Esperando eventos…</div>}
          </div>
        </div>
      </div>
    </>
  );
}
