import { withChannel } from "../channels";
import { Face } from "../components/Face";
import { Badge, PageHead, Progress, useApi } from "../components/ui";
import { elapsed } from "../format";
import { quoteFor, personaFor, bodyColor } from "../theme";
import { useLive } from "../store";
import type { AgentState } from "../types";

export default function Agents() {
  const channel = useLive((s) => s.channel);
  const theme = useLive((s) => s.theme);
  const { data } = useApi<{ agents: AgentState[]; pipeline: { id: string; number: number; title: string; agent: string | null }[] }>(withChannel("/api/agents", channel), { live: true });
  const { data: figures } = useApi<Record<string, unknown>>(`/api/profiles/${theme.id}/figures`);
  const live = useLive((s) => s.agents);
  const agents = (data?.agents ?? []).map((a) => live[a.name] ?? a);
  return (
    <>
      <PageHead title="Agentes" subtitle="El equipo de este canal: responsabilidades, fases y estadísticas reales de cada agente" />
      <div className="grid cols-3">
        {agents.map((a) => (
          <div key={a.name} className="panel" style={personaFor(theme, a.name) ? { borderTop: `3px solid ${bodyColor(theme, a)}` } : undefined}>
            {personaFor(theme, a.name) && (
              <div className="persona">
                <div className="row">
                  <Face theme={theme.id} agent={a.name} persona={personaFor(theme, a.name)} size={56} image={!!figures?.[a.name]} />
                  <div>
                    <b style={{ color: bodyColor(theme, a) }}>{personaFor(theme, a.name)!.character}</b>
                    <div className="muted">{personaFor(theme, a.name)!.epithet} · {personaFor(theme, a.name)!.alignment}</div>
                  </div>
                </div>
                <p className="quote">«{quoteFor(theme, a)}»</p>
              </div>
            )}
            <div className="row">
              <b>{a.title}</b>
              <span className="spacer" />
              <Badge status={a.status} />
            </div>
            <p className="muted mono">{a.name} · {a.uses_claude ? "usa Claude" : "sin Claude (determinista/medios)"}</p>
            <p className="muted">Fases: {a.phases.map((p) => data?.pipeline.find((x) => x.id === p)?.title ?? p).join(" · ")}</p>
            {a.status === "running" && (
              <>
                <p>{a.task}</p>
                <Progress value={a.progress} />
                <p className="mono">⏱ {elapsed(a.started_at)}</p>
              </>
            )}
            {a.last_result && <p>Último resultado: {a.last_result}</p>}
            {a.last_error && <p style={{ color: "var(--danger)" }}>Último error: {a.last_error}</p>}
            <div className="row mono muted">
              <span>{a.runs} ejecuciones</span>·<span>{a.errors} errores</span>·<span>{a.llm_calls} llamadas a Claude</span>
              {a.last_duration_s != null && <>·<span>última {a.last_duration_s}s</span></>}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
