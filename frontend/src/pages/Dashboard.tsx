import { tokens, withChannel } from "../channels";
import { ChannelArt } from "../components/ChannelArt";
import { Face } from "../components/Face";
import { Icon } from "../components/Icon";
import { Badge, ErrorBox, Progress, useApi } from "../components/ui";
import { AGENT_COLOR, describeEvent, eur, shortDate, statusLabel } from "../format";
import { useLive } from "../store";
import { displayName, personaFor } from "../theme";
import type { AgentState, Channel, ChannelOverview, ProjectSummary, YtEvent } from "../types";

interface Dash {
  projects: { total: number; by_status: Record<string, number> };
  waiting_approval: { id: string; name: string; gates: string[] }[];
  claude: { calls: number; seconds: number; lanes: Record<string, { paused: boolean; reason: string | null; concurrency: number }> };
  budget: { spent_month_eur: number; monthly_budget_eur: number | null } | null;
  agents: AgentState[];
}

const ROLE: Record<string, string> = {
  chief: "Jefe", director: "Director", scriptwriter: "Guionista", resources: "Recursos", voice: "Voz",
  editor: "Editor", sound: "Sonido", reviewer: "Revisor", publisher: "Publicador",
};
const ORDER = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];

/** Los 4 canales a la vez: qué está produciendo cada uno. Pulsar uno cambia de canal. */
function ChannelsOverview({ current, overview, channels }: { current: string; overview: ChannelOverview[]; channels: Channel[] }) {
  const setChannel = useLive((s) => s.setChannel);
  return (
    <section className="channels-overview" aria-label="Canales">
      {overview.map((o) => {
        const c = channels.find((x) => x.id === o.channel.id);
        return (
          <button key={o.channel.id} className={`ch-card${o.channel.id === current ? " current" : ""}`} style={{ ["--ch" as string]: o.accent }}
            onClick={() => setChannel(o.channel.id)} aria-pressed={o.channel.id === current}>
            <div className="ch-card-art"><ChannelArt profile={o.channel.theme} /></div>
            <div className="ch-card-head">
              <Face theme={o.channel.theme} agent="chief" persona={o.chief ?? c?.chief} size={52} image={c?.has_chief_image} ring={o.accent} />
              <div>
                <b>{o.channel.name}</b>
                <small>{(o.chief ?? c?.chief)?.character ?? "Jefe"}</small>
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
              <span><b>{o.projects.by_status.active ?? 0}</b>en curso</span>
              <span><b>{tokens(o.tokens_total)}</b>tokens</span>
              <span className={o.licenses.limited ? "warn" : ""}><b>{o.licenses.total}{o.licenses.limited ? "!" : ""}</b>licencias</span>
            </div>
          </button>
        );
      })}
    </section>
  );
}

function Kpi({ icon, label, value, foot }: { icon: string; label: string; value: React.ReactNode; foot?: React.ReactNode }) {
  return (
    <div className="panel kpi-card">
      <span className="kpi-icon"><Icon name={icon} size={20} /></span>
      <h2>{label}</h2>
      <div className="kpi">{value}</div>
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  );
}

export default function Dashboard() {
  const channel = useLive((s) => s.channel);
  const theme = useLive((s) => s.theme);
  const { data, error } = useApi<Dash>(withChannel("/api/dashboard", channel), { live: true });
  const { data: projects } = useApi<ProjectSummary[]>(withChannel("/api/projects", channel), { live: true });
  const { data: ov } = useApi<{ channels: ChannelOverview[]; claude_slots: number }>("/api/overview", { live: true, pollMs: 15000 });
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const ch = channels?.find((c) => c.id === channel);
  const profile = ch?.theme ?? theme.id;
  const { data: figures } = useApi<Record<string, unknown>>(`/api/profiles/${profile}/figures`);
  const allEvents = useLive((s) => s.events);
  const { data: recent } = useApi<YtEvent[]>(withChannel("/api/events?limit=60", channel));
  const liveEvents = allEvents.filter((e) => e.channel === channel);
  const seen = new Set(liveEvents.map((e) => e.at + e.type + e.agent));
  const events = [...liveEvents, ...[...(recent ?? [])].reverse().filter((e) => !seen.has(e.at + e.type + e.agent))].filter((e) => e.type !== "agent.progress");
  const liveAgents = useLive((s) => s.agents);
  const agentsList = Object.keys(liveAgents).length ? Object.values(liveAgents) : (data?.agents ?? []);
  const agents = [...agentsList].sort((a, b) => ORDER.indexOf(a.name) - ORDER.indexOf(b.name));
  const running = agents.filter((a) => a.status === "running").length;
  const me = ov?.channels.find((o) => o.channel.id === channel);
  const claudeLane = data?.claude.lanes.claude;

  return (
    <>
      <section className="hero">
        <ChannelArt profile={profile} />
        <div className="hero-body">
          <div style={{ flex: 1, minWidth: 260 }}>
            <h1 className="hero-title">{ch?.name ?? "YTAUTO"}</h1>
            <p className="hero-sub">{ch?.tagline ?? theme.room_subtitle}</p>
            <div className="hero-chips">
              <span className="hero-chip"><Icon name="projects" size={14} />{data?.projects.by_status.active ?? 0} en curso</span>
              <span className="hero-chip"><Icon name="bolt" size={14} />{running} trabajando ahora</span>
              <span className="hero-chip"><Icon name="coins" size={14} />{tokens(me?.tokens_total)} tokens</span>
              <span className="hero-chip"><Icon name="key" size={14} />{me?.licenses.total ?? 0} licencias</span>
            </div>
          </div>
          <div className="row">
            <div className="hero-director">
              <Face theme={profile} agent="chief" persona={ch?.chief} size={56} image={ch?.has_chief_image} ring={ch?.accent} />
              <div><small>Al mando</small><b>{ch?.chief?.character ?? "Jefe"}</b></div>
            </div>
            <a className="btn primary big" href="#/room"><Icon name="room" size={18} />Entrar en {theme.room_title}</a>
          </div>
        </div>
      </section>

      <ErrorBox error={error} />
      {claudeLane?.paused && (
        <div className="alert" style={{ marginTop: 14 }}><Icon name="alert" />Carril de Claude en pausa: {claudeLane.reason}. <a href="#/models">Gestionar</a></div>
      )}

      <h2 className="section-title">Tus 4 canales</h2>
      {ov && channels && <ChannelsOverview current={channel} overview={ov.channels} channels={channels} />}

      <h2 className="section-title">Este canal</h2>
      <div className="grid cols-4">
        <Kpi icon="projects" label="Proyectos" value={data?.projects.total ?? "—"} foot={`${data?.projects.by_status.completed ?? 0} terminados · ${data?.projects.by_status.active ?? 0} en curso`} />
        <Kpi icon="bell" label="Esperan tu decisión" value={data?.waiting_approval.length ?? "—"} foot={data?.waiting_approval.length ? "Revisa los proyectos marcados" : "Nada pendiente"} />
        <Kpi icon="sparkles" label="Llamadas a Claude" value={data?.claude.calls ?? "—"} foot={data ? `${Math.round(data.claude.seconds / 60)} min de trabajo` : ""} />
        <Kpi icon="wallet" label="Gasto externo (mes)" value={eur(data?.budget?.spent_month_eur ?? 0)}
          foot={data?.budget?.monthly_budget_eur != null ? `de ${eur(data.budget.monthly_budget_eur)}` : "sin límite fijado"} />
      </div>

      <h2 className="section-title">El equipo de {ch?.name ?? "este canal"}</h2>
      <div className="roster">
        {agents.map((a) => {
          const p = personaFor(theme, a.name);
          return (
            <a key={a.name} href={`#/room?agente=${a.name}`} className={`agent-card ${a.status}`} style={{ ["--agent" as string]: p?.color ?? "var(--accent)", color: "inherit" }}>
              <Face theme={profile} agent={a.name} persona={p} size={50} image={!!figures?.[a.name]} />
              <div>
                <span className="role">{ROLE[a.name]}</span>
                <b className="ellipsis">{displayName(theme, a)}</b>
                <span className="doing ellipsis">{a.status === "running" ? a.task ?? "Trabajando" : a.last_result ?? statusLabel(a.status)}</span>
                {a.status === "running" ? <Progress value={a.progress} /> : <span className="small" style={{ color: AGENT_COLOR[a.status] }}>● {statusLabel(a.status)}</span>}
              </div>
            </a>
          );
        })}
      </div>

      <div className="grid cols-2" style={{ marginTop: 22 }}>
        <div className="panel">
          <h2>Producciones recientes</h2>
          {data?.waiting_approval.length ? (
            <div className="alert"><Icon name="bell" />
              <span>Esperan tu decisión: {data.waiting_approval.map((w) => <a key={w.id} href={`#/projects/${w.id}`} style={{ marginRight: 8 }}>{w.name}</a>)}</span>
            </div>
          ) : null}
          {projects?.length ? (
            <table>
              <tbody>
                {projects.slice(0, 7).map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => (location.hash = `#/projects/${p.id}`)}>
                    <td><b>{p.name}</b><div className="muted small">{shortDate(p.created_at)} · {p.duration_s} s</div></td>
                    <td style={{ width: 130 }}><Progress value={p.progress} /></td>
                    <td style={{ width: 120 }}><Badge status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">Aún no hay producciones. <a href="#/new">Crea el primer vídeo</a></div>
          )}
        </div>
        <div className="panel">
          <h2>Actividad en directo</h2>
          <div className="feed">
            {events.slice(0, 30).map((e, i) => (
              <div key={i} className="feed-item">
                <i style={{ background: personaFor(theme, e.agent ?? "")?.color ?? "var(--muted)" }} />
                <span><span className="who">{e.agent ? personaFor(theme, e.agent)?.character ?? ROLE[e.agent] ?? e.agent : "Sistema"}</span>{describeEvent(e.type, e.data)}</span>
                <time>{new Date(e.at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}</time>
              </div>
            ))}
            {!events.length && <div className="empty">Esperando actividad…</div>}
          </div>
        </div>
      </div>
    </>
  );
}
