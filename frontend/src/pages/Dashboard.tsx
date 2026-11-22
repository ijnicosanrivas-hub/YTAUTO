import { displayName } from "../theme";
import { tokens, withChannel } from "../channels";
import { Face } from "../components/Face";
import { AGENT_COLOR, describeEvent, eur, shortDate } from "../format";
import { Badge, ErrorBox, PageHead, Progress, useApi } from "../components/ui";
import { useLive } from "../store";
import type { AgentState, Channel, ChannelOverview, ProjectSummary, YtEvent } from "../types";

const ROLE: Record<string, string> = {
  chief: "Jefe", director: "Director", scriptwriter: "Guionista", resources: "Recursos", voice: "Voz",
  editor: "Editor", sound: "Sonido", reviewer: "Revisor", publisher: "Publicador",
};

/** Los 4 canales a la vez: qué está produciendo cada uno ahora mismo. Pulsar uno cambia de canal. */
function ChannelsOverview({ current }: { current: string }) {
  const { data } = useApi<{ channels: ChannelOverview[]; claude_slots: number }>("/api/overview", { live: true, pollMs: 15000 });
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const setChannel = useLive((s) => s.setChannel);
  if (!data) return null;
  return (
    <section className="channels-overview" aria-label="Canales">
      {data.channels.map((o) => {
        const c = channels?.find((x) => x.id === o.channel.id);
        const active = o.projects.by_status.active ?? 0;
        return (
          <button key={o.channel.id} className={`ch-card${o.channel.id === current ? " current" : ""}`} style={{ ["--ch" as string]: o.accent }}
            onClick={() => setChannel(o.channel.id)}>
            <div className="ch-card-head">
              <Face theme={o.channel.theme} agent="director" persona={o.director} size={46} image={c?.has_director_image} ring={o.accent} />
              <div>
                <b>{o.channel.name}</b>
                <small>{o.channel.tagline}</small>
              </div>
              <span className={`pulse ${o.running_agents.length ? "on" : ""}`} title={o.running_agents.length ? "Produciendo" : "En espera"} />
            </div>
            <div className="ch-card-now">
              {o.running_agents.length ? (
                o.running_agents.slice(0, 2).map((a) => (
                  <div key={a.name} className="now-row">
                    <span>{ROLE[a.name] ?? a.name}</span>
                    <span className="muted ellipsis">{a.task ?? "trabajando"}</span>
                    <Progress value={a.progress} />
                  </div>
                ))
              ) : (
                <div className="muted">{o.current ? `En curso: ${o.current.name}` : "Sin producción en marcha"}</div>
              )}
            </div>
            <div className="ch-card-stats">
              <span><b>{active}</b> en curso</span>
              <span><b>{o.projects.by_status.completed ?? 0}</b> hechos</span>
              <span><b>{o.waiting_agents}</b> esperan</span>
              <span><b>{tokens(o.tokens_total)}</b> tokens</span>
              <span className={o.licenses.limited ? "warn" : ""}><b>{o.licenses.total}</b> lic.{o.licenses.limited ? ` (${o.licenses.limited} agotada)` : ""}</span>
            </div>
          </button>
        );
      })}
    </section>
  );
}

interface Dash {
  projects: { total: number; by_status: Record<string, number> };
  waiting_approval: { id: string; name: string; gates: string[] }[];
  claude: { calls: number; seconds: number; lanes: Record<string, { paused: boolean; reason: string | null; concurrency: number }> };
  budget: { spent_month_eur: number; monthly_budget_eur: number | null } | null;
  agents: AgentState[];
}

export default function Dashboard() {
  const channel = useLive((s) => s.channel);
  const { data, error } = useApi<Dash>(withChannel("/api/dashboard", channel), { live: true });
  const { data: projects } = useApi<ProjectSummary[]>(withChannel("/api/projects", channel), { live: true });
  const allEvents = useLive((s) => s.events);
  const liveEvents = allEvents.filter((e) => e.channel === channel);
  // Historial reciente persistido + eventos que llegan en directo (sin duplicar)
  const { data: recent } = useApi<YtEvent[]>(withChannel("/api/events?limit=60", channel));
  const seen = new Set(liveEvents.map((e) => e.at + e.type + e.agent));
  const events = [...liveEvents, ...[...(recent ?? [])].reverse().filter((e) => !seen.has(e.at + e.type + e.agent))];
  const liveAgents = useLive((s) => s.agents);
  const theme = useLive((s) => s.theme);
  const agents = Object.keys(liveAgents).length ? Object.values(liveAgents) : (data?.agents ?? []);
  const claudeLane = data?.claude.lanes.claude;

  return (
    <>
      <PageHead title="Panel general" subtitle="Los 4 canales en paralelo. Debajo, el detalle del canal seleccionado">
        <a className="btn primary" href="#/new">
          + Nuevo vídeo
        </a>
      </PageHead>
      <ChannelsOverview current={channel} />
      <h2 className="section-title">Canal {theme.name === "Clásico" ? channel : theme.brand}</h2>
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
          <h2>Llamadas a Claude (canal)</h2>
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
                    <span style={{ color: AGENT_COLOR[a.status] }}>●</span> {displayName(theme, a)}{theme.agents[a.name] ? <span className="muted"> · {a.title}</span> : null}
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
