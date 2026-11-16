import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge, ErrorBox, PageHead, useAction, useApi } from "../components/ui";

interface ModelsData {
  config: { default: string; fallback: string; agents: Record<string, string>; concurrency: number; max_concurrency: number };
  aliases: string[];
  usage_by_agent: Record<string, { calls: number; seconds: number; models: Record<string, number> }>;
  llm_provider: string;
  lanes: Record<string, { paused: boolean; reason: string | null; resume_at: number | null; concurrency: number }>;
  note: string;
}

const AGENTS = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];

export default function Models() {
  const { data, reload } = useApi<ModelsData>("/api/models", { live: true });
  const [agents, setAgents] = useState<Record<string, string>>({});
  const [conc, setConc] = useState(1);
  const { busy, error, run } = useAction();
  useEffect(() => {
    if (data) {
      setAgents(data.config.agents);
      setConc(data.lanes.claude?.concurrency ?? 1);
    }
  }, [data]);
  const lane = data?.lanes.claude;

  return (
    <>
      <PageHead title="Control de modelos Claude" subtitle="Una única licencia Claude Pro, usada a través de Claude Code (sin API)" />
      <ErrorBox error={error} />
      {lane?.paused && (
        <div className="alert">
          Carril de Claude en pausa: {lane.reason}
          {lane.resume_at ? ` · reanudación automática ${new Date(lane.resume_at * 1000).toLocaleString("es-ES")}` : " · reanudación manual"}
          <button className="btn" style={{ marginLeft: 10 }} disabled={busy} onClick={async () => { await run(() => api.post("/api/queue/claude/resume")); void reload(); }}>
            Reanudar ahora
          </button>
        </div>
      )}
      <div className="grid cols-2">
        <div className="panel">
          <h2>Modelo por agente</h2>
          <p className="muted">Se usan alias (sonnet, opus, haiku) para tener siempre la versión más reciente. Si un modelo no está disponible en tu plan, se usa el de respaldo ({data?.config.fallback}).</p>
          <table>
            <tbody>
              {AGENTS.map((a) => (
                <tr key={a}>
                  <td>{a}</td>
                  <td>
                    <select value={agents[a] ?? data?.config.default ?? "sonnet"} onChange={(e) => setAgents((s) => ({ ...s, [a]: e.target.value }))}>
                      {(data?.aliases ?? []).map((m) => <option key={m}>{m}</option>)}
                    </select>
                  </td>
                  <td className="muted mono">
                    {data?.usage_by_agent[a] ? `${data.usage_by_agent[a].calls} llamadas · ${Math.round(data.usage_by_agent[a].seconds)} s` : "sin uso"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button className="btn primary" style={{ marginTop: 10 }} disabled={busy} onClick={async () => { await run(() => api.put("/api/models", { agents })); void reload(); }}>
            Guardar modelos
          </button>
        </div>
        <div className="panel">
          <h2>Motor y concurrencia</h2>
          <p>Motor: <Badge status={data?.llm_provider === "claude_cli" ? "completed" : "in_review"} label={data?.llm_provider === "claude_cli" ? "Claude Code (sesión Pro)" : `${data?.llm_provider} (sin Claude)`} /></p>
          <label className="field">Tareas de Claude simultáneas (máx. {data?.config.max_concurrency})
            <input type="number" min={1} max={data?.config.max_concurrency ?? 2} value={conc} onChange={(e) => setConc(Number(e.target.value))} />
          </label>
          <button className="btn" style={{ marginTop: 8 }} disabled={busy} onClick={async () => { await run(() => api.put("/api/queue/concurrency", { lane: "claude", concurrency: conc })); void reload(); }}>
            Aplicar (al reiniciar el worker)
          </button>
          <p className="muted">Recomendado: 1. Una concurrencia mayor no aumenta tu cuota; solo agota antes la ventana de uso.</p>
          <h2 style={{ marginTop: 14 }}>Modelos servidos</h2>
          <table><tbody>{Object.entries(data?.usage_by_agent ?? {}).flatMap(([a, u]) => Object.entries(u.models).map(([m, n]) => <tr key={a + m}><td>{a}</td><td className="mono">{m}</td><td>{n}</td></tr>))}</tbody></table>
          <p className="muted">{data?.note}</p>
        </div>
      </div>
    </>
  );
}
