import { useState } from "react";
import { api } from "../api";
import { groupByChannel, tokens } from "../channels";
import { Icon } from "../components/Icon";
import { ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import { shortDate } from "../format";
import { useLive } from "../store";
import type { Channel, License, LicensesView, UsageBlock } from "../types";

const PLANS = ["Pro", "Max 5x", "Max 20x", "Team", "API"];
const AGENT_LABEL: Record<string, string> = {
  chief: "Jefe", director: "Director", scriptwriter: "Guionista", resources: "Recursos", voice: "Voz",
  editor: "Editor", sound: "Sonido", reviewer: "Revisor", publisher: "Publicador",
};

interface Draft {
  id?: string;
  name: string;
  channel_id: string;
  kind: "claude_session" | "api_key";
  plan: string;
  monthly_token_limit: string;
  api_key: string;
  config_dir: string;
  notes: string;
  enabled: boolean;
}

const emptyDraft = (channel: string): Draft => ({
  name: "", channel_id: channel, kind: "claude_session", plan: "Pro", monthly_token_limit: "", api_key: "", config_dir: "", notes: "", enabled: true,
});

/** Barras de los últimos 14 días. */
function Spark({ daily, color }: { daily: UsageBlock["daily"]; color: string }) {
  const max = Math.max(1, ...daily.map((d) => d.tokens));
  return (
    <div className="spark" role="img" aria-label="Tokens por día, últimos 14 días">
      {daily.map((d) => (
        <span key={d.day} title={`${d.day}: ${tokens(d.tokens)} tokens`}>
          <i style={{ height: `${Math.max(3, (d.tokens / max) * 100)}%`, background: d.tokens ? color : undefined }} />
        </span>
      ))}
    </div>
  );
}

function AgentBars({ by, color }: { by: Record<string, number>; color: string }) {
  const rows = Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = Math.max(1, ...rows.map((r) => r[1]));
  if (!rows.length) return <div className="muted small">Sin consumo este mes</div>;
  return (
    <div className="hbars">
      {rows.map(([a, t]) => (
        <div key={a} className="hbar">
          <span>{AGENT_LABEL[a] ?? a}</span>
          <span className="hbar-track"><i style={{ width: `${(t / max) * 100}%`, background: color }} /></span>
          <span className="mono">{tokens(t)}</span>
        </div>
      ))}
    </div>
  );
}

function LicenseCard({ l, color, channelName, onEdit, onChanged }: {
  l: License; color: string; channelName: (id: string) => string; onEdit: () => void; onChanged: () => void;
}) {
  const { busy, error, run } = useAction();
  const status = l.status === "limited" ? { cls: "s-error", text: "Agotada" } : l.status === "disabled" ? { cls: "s-paused", text: "Desactivada" } : { cls: "s-completed", text: "Disponible" };
  const pct = l.usage_pct;
  const borrowed = Object.keys(l.by_channel).filter((c) => c !== l.channel_id && c !== "?");
  const loginCmd = l.config_dir ? `set CLAUDE_CONFIG_DIR=${l.config_dir}&& claude /login` : "";
  return (
    <div className={`panel lic-card ${l.status}`} style={{ ["--lic" as string]: color }}>
      <div className="row">
        <div>
          <h3 className="lic-name">{l.name}</h3>
          <div className="muted small">{l.plan || "Sin plan"} · {l.kind === "api_key" ? `Clave de API ${l.secret_hint ?? ""}` : "Sesión de Claude Code"}</div>
        </div>
        <span className="spacer" />
        <span className={`badge ${status.cls}`}>{status.text}</span>
      </div>
      <ErrorBox error={error} />
      <div className="lic-big">
        <b>{tokens(l.tokens.month)}</b>
        <span className="muted">tokens este mes{l.monthly_token_limit ? ` de ${tokens(l.monthly_token_limit)}` : ""}</span>
      </div>
      <div className="meter" aria-label="Uso mensual">
        <i style={{ width: `${Math.min(100, pct ?? 0)}%`, background: pct != null && pct >= 90 ? "var(--danger)" : pct != null && pct >= 70 ? "var(--warn)" : color }} />
      </div>
      <div className="muted small">{pct != null ? `${pct} % de la referencia mensual` : "Sin referencia mensual (añádela para ver el %)"}</div>
      <div className="lic-stats">
        <div><small>Hoy</small><b>{tokens(l.tokens.today)}</b></div>
        <div><small>7 días</small><b>{tokens(l.tokens.d7)}</b></div>
        <div><small>30 días</small><b>{tokens(l.tokens.d30)}</b></div>
        <div><small>Llamadas mes</small><b>{l.calls.month}</b></div>
      </div>
      <Spark daily={l.daily} color={color} />
      <div className="lic-cols">
        <div>
          <h4>Por agente (mes)</h4>
          <AgentBars by={l.by_agent} color={color} />
        </div>
        <div>
          <h4>Detalle</h4>
          <div className="kv"><span>Entrada</span><b className="mono">{tokens(l.input_tokens)}</b></div>
          <div className="kv"><span>Salida</span><b className="mono">{tokens(l.output_tokens)}</b></div>
          <div className="kv"><span>Caché leída</span><b className="mono">{tokens(l.cache_read_tokens)}</b></div>
          <div className="kv"><span>Equivalente API</span><b className="mono">{l.cost_usd_eq.toFixed(2)} $</b></div>
          <div className="kv"><span>Último uso</span><b>{l.last_used_at ? shortDate(l.last_used_at) : "—"}</b></div>
        </div>
      </div>
      {borrowed.length > 0 && <div className="muted small">También la usó: {borrowed.map(channelName).join(", ")}</div>}
      {l.limited_now && <div className="alert">{l.limited_reason ?? "Límite de uso alcanzado"}{l.limited_until ? ` · reinicio ${new Date(l.limited_until * 1000).toLocaleString("es-ES")}` : ""}</div>}
      {l.kind === "claude_session" && (
        <details className="login-help">
          <summary>Iniciar sesión con esta licencia</summary>
          <p className="muted small">Una vez, en una ventana de comandos (cmd) del PC, con la cuenta de esta licencia:</p>
          <code className="mono copy" onClick={() => void navigator.clipboard?.writeText(loginCmd)} title="Copiar">{loginCmd}</code>
        </details>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        {l.limited_now && (
          <button className="btn" disabled={busy} onClick={async () => { if (await run(() => api.post(`/api/licenses/${l.id}/reset`))) onChanged(); }}>
            Ya tiene uso disponible
          </button>
        )}
        <button className="btn" onClick={onEdit}>Editar</button>
        <span className="spacer" />
        <button className="btn danger" disabled={busy} onClick={async () => {
          if (!confirm(`¿Eliminar la licencia «${l.name}»? Los proyectos que la usen pasarán a la del canal.`)) return;
          if (await run(() => api.del(`/api/licenses/${l.id}`))) onChanged();
        }}>Eliminar</button>
      </div>
    </div>
  );
}

function LicenseForm({ draft, channels, onDone }: { draft: Draft; channels: { id: string; name: string }[]; onDone: () => void }) {
  const [d, setD] = useState(draft);
  const { busy, error, run } = useAction();
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((x) => ({ ...x, [k]: v }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = {
      name: d.name, channel_id: d.channel_id, kind: d.kind, plan: d.plan, enabled: d.enabled, notes: d.notes || null,
      monthly_token_limit: d.monthly_token_limit ? Number(d.monthly_token_limit) : null,
      api_key: d.kind === "api_key" && d.api_key ? d.api_key : null,
      config_dir: d.kind === "claude_session" && d.config_dir ? d.config_dir : null,
    };
    const ok = await run(() => (d.id ? api.put(`/api/licenses/${d.id}`, body) : api.post("/api/licenses", body)));
    if (ok) onDone();
  };
  return (
    <form className="panel" onSubmit={submit} style={{ marginBottom: 14 }}>
      <h2>{d.id ? "Editar licencia" : "Nueva licencia"}</h2>
      <ErrorBox error={error} />
      <div className="form-grid">
        <label className="field">Nombre *<input required value={d.name} onChange={(e) => set("name", e.target.value)} placeholder="p. ej. Pro GTA 1" /></label>
        <label className="field">Canal dueño
          <select value={d.channel_id} onChange={(e) => set("channel_id", e.target.value)}>
            {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Tipo
          <select value={d.kind} onChange={(e) => set("kind", e.target.value as Draft["kind"])}>
            <option value="claude_session">Sesión de Claude Code (suscripción)</option>
            <option value="api_key">Clave de API de Anthropic</option>
          </select>
        </label>
        <label className="field">Plan
          <select value={d.plan} onChange={(e) => set("plan", e.target.value)}>
            {PLANS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label className="field">Referencia mensual de tokens
          <input type="number" min={0} step={100000} value={d.monthly_token_limit} onChange={(e) => set("monthly_token_limit", e.target.value)} placeholder="opcional" />
        </label>
        {d.kind === "api_key" ? (
          <label className="field">Clave de API {d.id ? "(vacío = no cambiar)" : "*"}
            <input type="password" autoComplete="off" required={!d.id} value={d.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder="sk-ant-…" />
          </label>
        ) : (
          <label className="field">Carpeta de la sesión (opcional)
            <input value={d.config_dir} onChange={(e) => set("config_dir", e.target.value)} placeholder="se crea una propia en data\licencias" />
          </label>
        )}
        <label className="field wide">Notas<input value={d.notes} onChange={(e) => set("notes", e.target.value)} /></label>
        <label className="row wide" style={{ color: "var(--text)" }}>
          <input type="checkbox" checked={d.enabled} onChange={(e) => set("enabled", e.target.checked)} /> Activa
        </label>
      </div>
      <p className="muted small">
        Cada licencia es una cuenta distinta: el programa nunca la usa para dos llamadas a la vez y, si se agota, solo se para lo que dependa
        de ella. La clave de API se guarda cifrada en tu PC y nunca se muestra entera.
      </p>
      <div className="row">
        <span className="spacer" />
        <button type="button" className="btn" onClick={onDone}>Cancelar</button>
        <button className="btn primary" disabled={busy}>{busy ? "Guardando…" : "Guardar"}</button>
      </div>
    </form>
  );
}

export default function Licenses() {
  const { data, error, reload } = useApi<LicensesView>("/api/licenses", { live: true, pollMs: 30000 });
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const current = useLive((s) => s.channel);
  const [editing, setEditing] = useState<Draft | null>(null);
  const order = (data?.channels ?? []).map((c) => c.id);
  const color = (id: string) => channels?.find((c) => c.id === id)?.accent ?? "var(--accent)";
  const channelName = (id: string) => data?.channels.find((c) => c.id === id)?.name ?? id;
  const lics = data?.licenses ?? [];
  const limited = lics.filter((l) => l.limited_now).length;
  const done = () => { setEditing(null); void reload(); };
  return (
    <>
      <PageHead title="Licencias de Claude" subtitle="Pool de licencias de los 4 canales: consumo de tokens, estado y estadísticas de uso">
        <button className="btn primary" onClick={() => setEditing(emptyDraft(current))}>+ Añadir licencia</button>
      </PageHead>
      <ErrorBox error={error} />
      <div className="grid cols-4">
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="coins" size={20} /></span><h2>Tokens este mes</h2><div className="kpi">{tokens(data?.totals.tokens_month)}</div><div className="kpi-foot">entre los 4 canales</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="sparkles" size={20} /></span><h2>Llamadas este mes</h2><div className="kpi">{data?.totals.calls_month ?? "—"}</div><div className="kpi-foot">a Claude, todas las licencias</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="key" size={20} /></span><h2>Licencias</h2><div className="kpi">{lics.length}</div><div className="kpi-foot" style={limited ? { color: "var(--danger)" } : undefined}>{limited ? `${limited} agotada${limited > 1 ? "s" : ""} ahora` : "todas disponibles"}</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="bolt" size={20} /></span><h2>Llamadas simultáneas</h2><div className="kpi">{data?.claude_slots ?? "—"}</div><div className="kpi-foot">una por licencia, nunca dos</div></div>
      </div>
      {editing && <div style={{ marginTop: 14 }}><LicenseForm draft={editing} channels={data?.channels ?? []} onDone={done} /></div>}
      {groupByChannel(lics, order).map(([ch, list]) => (
        <section key={ch} className="lic-group" style={{ ["--lic" as string]: color(ch) }}>
          <div className="lic-group-head">
            <span className="dot" style={{ background: color(ch) }} />
            <h2>{channelName(ch)}</h2>
            <span className="muted">{list.length ? `${list.length} licencia${list.length > 1 ? "s" : ""} · ${tokens(list.reduce((a, l) => a + l.tokens.month, 0))} tokens este mes` : "sin licencias propias: usa la sesión principal"}</span>
            <span className="spacer" />
            <button className="btn small" onClick={() => setEditing(emptyDraft(ch))}>+ Añadir</button>
          </div>
          {list.length > 0 && (
            <div className="lic-grid">
              {list.map((l) => (
                <LicenseCard key={l.id} l={l} color={color(ch)} channelName={channelName} onChanged={() => void reload()}
                  onEdit={() => setEditing({ id: l.id, name: l.name, channel_id: l.channel_id, kind: l.kind, plan: l.plan || "Pro", enabled: l.enabled,
                    monthly_token_limit: l.monthly_token_limit ? String(l.monthly_token_limit) : "", api_key: "", config_dir: l.config_dir ?? "", notes: l.notes ?? "" })} />
              ))}
            </div>
          )}
        </section>
      ))}
      {data?.default && (
        <section className="lic-group">
          <div className="lic-group-head"><span className="dot" /><h2>Sesión principal (sin licencia asignada)</h2>
            <span className="muted">{tokens(data.default.tokens.month)} tokens este mes · {data.default.calls.month} llamadas</span></div>
          <div className="panel"><Spark daily={data.default.daily} color="var(--muted)" /></div>
        </section>
      )}
      <p className="muted small">
        Los tokens salen de lo que informa Claude Code en cada llamada (entrada + salida + escritura de caché). Las suscripciones no publican un
        límite en tokens: la «referencia mensual» es tuya, para ver el % de uso. El «equivalente API» es orientativo, no una factura.
      </p>
    </>
  );
}
