import { useEffect, useState } from "react";
import { api } from "../api";
import { groupByChannel, tokens } from "../channels";
import { Icon } from "../components/Icon";
import { ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import { STATUS, ago, clock, duration, meterTone, minutesUntil } from "../monitor";
import type { Channel, License, LiveLicense, LiveUsage, LiveView } from "../types";

const ROLE: Record<string, string> = {
  chief: "Jefe", director: "Director", scriptwriter: "Guionista", resources: "Recursos", voice: "Voz",
  editor: "Editor", sound: "Sonido", reviewer: "Revisor", publisher: "Publicador",
};

/** Barra de consumo con la marca del aviso (80 %). El estado se dice siempre con texto, no solo con color. */
function Meter({ label, used, limit, pct, unit = "tokens", warn }: { label: string; used: string; limit: string | null; pct: number | null; unit?: string; warn: number }) {
  const tone = meterTone(pct, warn);
  return (
    <div className="lm">
      <div className="lm-head">
        <span>{label}</span>
        <b>{used}{limit ? <span className="muted"> / {limit} {unit}</span> : <span className="muted"> {unit} · sin límite</span>}</b>
      </div>
      <div className={`lm-track ${tone}`} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? 0} aria-label={label}>
        <i style={{ width: `${Math.min(100, pct ?? 0)}%` }} />
        {limit && <s style={{ left: `${warn}%` }} title={`Aviso al ${warn} %`} />}
      </div>
    </div>
  );
}

/** Tokens de las últimas 2 horas en tramos de 5 minutos (un solo dato: no necesita leyenda). */
function Spark({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(1, ...data);
  const now = Date.now();
  return (
    <div className="lspark" role="img" aria-label="Tokens por cada 5 minutos, últimas 2 horas">
      {data.map((v, i) => {
        const from = new Date(now - (data.length - i) * 5 * 60000);
        return (
          <span key={i} title={`${from.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}: ${tokens(v)} tokens`}>
            <i style={{ height: `${v ? Math.max(6, (v / max) * 100) : 3}%`, background: v ? color : undefined }} />
          </span>
        );
      })}
    </div>
  );
}

function LimitsEditor({ l, onSaved }: { l: LiveLicense; onSaved: () => void }) {
  const [h5, setH5] = useState(l.budget_5h_tokens ? String(l.budget_5h_tokens) : "");
  const [wk, setWk] = useState(l.budget_week_tokens ? String(l.budget_week_tokens) : "");
  const [usd, setUsd] = useState(l.budget_month_usd ? String(l.budget_month_usd) : "");
  const { busy, error, run } = useAction();
  const num = (v: string) => (v.trim() ? Number(v) : null);
  return (
    <details className="lm-edit">
      <summary>Ajustar límites</summary>
      <ErrorBox error={error} />
      <div className="lm-edit-grid">
        <label className="field">Ventana de 5 h (tokens)<input type="number" min={0} step={50000} value={h5} onChange={(e) => setH5(e.target.value)} placeholder={l.observed_5h_tokens ? `observado: ${l.observed_5h_tokens}` : "sin límite"} /></label>
        <label className="field">Semana (tokens)<input type="number" min={0} step={100000} value={wk} onChange={(e) => setWk(e.target.value)} placeholder="sin límite" /></label>
        <label className="field">Gasto del mes ($){l.kind === "api_key" ? "" : " · solo API"}<input type="number" min={0} step={1} value={usd} onChange={(e) => setUsd(e.target.value)} placeholder="sin límite" /></label>
      </div>
      <div className="row">
        <span className="muted small">Al llegar a un límite la licencia se frena sola y se libera cuando la ventana deja sitio.</span>
        <span className="spacer" />
        <button className="btn small primary" disabled={busy} onClick={async () => {
          if (await run(() => api.put(`/api/licenses/${l.id}/limits`, { budget_5h_tokens: num(h5), budget_week_tokens: num(wk), budget_month_usd: num(usd) }))) onSaved();
        }}>{busy ? "Guardando…" : "Guardar límites"}</button>
      </div>
    </details>
  );
}

function LiveCard({ l, color, warn, now, onChanged }: { l: LiveLicense; color: string; warn: number; now: number; onChanged: () => void }) {
  const st = STATUS[l.status];
  const stopped = l.status === "freno" || l.status === "agotada";
  const reset = l.limited_until ?? l.brake?.until ?? null;
  const { busy, run } = useAction();
  return (
    <article className={`panel lcard ${l.status}`} style={{ ["--lic" as string]: color }}>
      <header className="lcard-head">
        <div>
          <h3>{l.name}</h3>
          <span className="muted small">{l.plan || "Sin plan"} · {l.kind === "api_key" ? "Clave de API" : "Sesión de Claude Code"}</span>
        </div>
        <span className="spacer" />
        {l.in_flight > 0 && <span className="live-pill"><i />Trabajando</span>}
        <span className={`badge ${st.cls}`}><Icon name={st.icon} size={13} />{st.label}</span>
      </header>

      <div className="lcard-big">
        {stopped ? (
          <><b>0</b><span className="muted">{l.status === "agotada" ? "Claude ha cortado esta cuenta" : "frenada por tu límite"}{reset ? ` · vuelve a las ${clock(reset)}` : ""}</span></>
        ) : l.limit_5h ? (
          <><b>{tokens(l.remaining_5h)}</b><span className="muted">tokens libres en la ventana de 5 h{l.limit_5h_source === "observado" ? " (límite real observado)" : ""}</span></>
        ) : (
          <><b>{tokens(l.used_5h)}</b><span className="muted">tokens en las últimas 5 h · pon un límite para ver cuánto queda</span></>
        )}
      </div>

      <Meter label="Ventana de 5 h" used={tokens(l.used_5h)} limit={l.limit_5h ? tokens(l.limit_5h) : null} pct={l.pct_5h} warn={warn} />
      <Meter label="Últimos 7 días" used={tokens(l.used_week)} limit={l.limit_week ? tokens(l.limit_week) : null} pct={l.pct_week} warn={warn} />
      {(l.kind === "api_key" || l.limit_usd) && (
        <Meter label="Gasto del mes" used={`${l.usd_month.toFixed(2)}`} limit={l.limit_usd ? l.limit_usd.toFixed(2) : null} pct={l.pct_usd} unit="$" warn={warn} />
      )}

      <div className="lcard-facts">
        <div><small>Ritmo ahora</small><b>{tokens(Math.round(l.burn_per_min))}<span className="muted"> /min</span></b></div>
        <div><small>Se acaba en</small><b>{l.eta_min != null ? duration(l.eta_min) : l.limit_5h ? "no se acaba a este ritmo" : "—"}</b></div>
        <div><small>Ventana se libera</small><b>{l.window_frees_at ? `${clock(l.window_frees_at)} · ${duration(minutesUntil(l.window_frees_at, now))}` : "—"}</b></div>
        <div><small>Llamadas 5 h</small><b>{l.calls_5h}</b></div>
      </div>

      <Spark data={l.spark} color={color} />

      {stopped && (
        <div className="alert err">
          <Icon name="alert" />
          <span>
            {l.limited_reason ?? l.brake?.reason}. {reset ? `Vuelve a estar disponible a las ${clock(reset)} (en ${duration(minutesUntil(reset, now))}).` : "Disponible cuando lo indiques."}
            {" "}Solo se para lo que depende de esta licencia: los demás canales siguen.
          </span>
        </div>
      )}

      {l.recent.length > 0 && (
        <ul className="lcard-recent">
          {l.recent.slice(0, 4).map((r) => (
            <li key={r.at + r.agent}><span>{ROLE[r.agent ?? ""] ?? r.agent ?? "—"}</span><b className="mono">{tokens(r.tokens)}</b><time>{ago(r.at, now)}</time></li>
          ))}
        </ul>
      )}

      <div className="row">
        <LimitsEditor l={l} onSaved={onChanged} />
        {l.status === "agotada" && (
          <button className="btn small" disabled={busy} onClick={async () => { if (await run(() => api.post(`/api/licenses/${l.id}/reset`))) onChanged(); }}>
            Ya tiene uso disponible
          </button>
        )}
      </div>
    </article>
  );
}

function DefaultCard({ d, now }: { d: LiveUsage; now: number }) {
  if (!d.used_week && !d.in_flight) return null;
  return (
    <section className="lic-group">
      <div className="lic-group-head"><span className="dot" /><h2>Sesión principal</h2><span className="muted">sin licencia asignada (la del PC)</span></div>
      <div className="panel">
        <div className="lcard-facts">
          <div><small>Últimas 5 h</small><b>{tokens(d.used_5h)}</b></div>
          <div><small>7 días</small><b>{tokens(d.used_week)}</b></div>
          <div><small>Ritmo</small><b>{tokens(Math.round(d.burn_per_min))} /min</b></div>
          <div><small>Última llamada</small><b>{d.recent[0] ? ago(d.recent[0].at, now) : "—"}</b></div>
        </div>
        <Spark data={d.spark} color="var(--muted)" />
      </div>
    </section>
  );
}

export default function Monitor() {
  // En vivo: se recarga con cada llamada que empieza o termina (eventos «license.usage») y, como respaldo, cada 5 s.
  const { data, error, reload } = useApi<LiveView>("/api/licenses/live", { live: true, pollMs: 5000 });
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000); // relojes y cuentas atrás
    return () => clearInterval(t);
  }, []);
  const color = (id: string) => channels?.find((c) => c.id === id)?.accent ?? "var(--accent)";
  const lics = data?.licenses ?? [];
  const order = (data?.channels ?? []).map((c) => c.id);
  const t = data?.totals;
  return (
    <>
      <PageHead title="Monitor de tokens" subtitle="Consumo en vivo de cada licencia: se actualiza solo con cada llamada a Claude, sin recargar." />
      <div className="alert info">
        <Icon name="live" />
        <span>
          Claude no publica cuánto le queda a una suscripción, así que el saldo se calcula aquí: se suman los tokens de cada llamada
          y se comparan con el límite que pongas a cada licencia. Si Claude corta una cuenta, se apunta lo gastado hasta ese momento
          y se usa como su límite real. Al llegar al límite, la licencia se frena sola antes de gastar de más.
        </span>
      </div>
      <ErrorBox error={error} />
      <div className="grid cols-4">
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="coins" size={20} /></span><h2>Tokens últimas 5 h</h2><div className="kpi">{tokens(t?.used_5h)}</div><div className="kpi-foot">todas las licencias</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="trend" size={20} /></span><h2>Ritmo ahora</h2><div className="kpi">{tokens(Math.round(t?.burn_per_min ?? 0))}<small>tokens/min</small></div><div className="kpi-foot">media de los últimos 15 min</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="bolt" size={20} /></span><h2>Llamadas en curso</h2><div className="kpi">{t?.in_flight ?? 0}</div><div className="kpi-foot">una como máximo por licencia</div></div>
        <div className="panel kpi-card"><span className="kpi-icon"><Icon name="alert" size={20} /></span><h2>Frenadas o agotadas</h2><div className="kpi">{t?.stopped ?? 0}</div><div className="kpi-foot">{t?.warning ? `${t.warning} cerca del límite` : "ninguna cerca del límite"}</div></div>
      </div>
      {groupByChannel(lics as unknown as License[], order).map(([ch, list]) => (
        <section key={ch} className="lic-group">
          <div className="lic-group-head">
            <span className="dot" style={{ background: color(ch) }} />
            <h2>{data?.channels.find((c) => c.id === ch)?.name ?? ch}</h2>
            <span className="muted">{list.length ? `${list.length} licencia${list.length > 1 ? "s" : ""}` : "sin licencias propias"}</span>
          </div>
          {list.length > 0 && (
            <div className="lic-grid">
              {(list as unknown as LiveLicense[]).map((l) => <LiveCard key={l.id} l={l} color={color(ch)} warn={data?.warn_pct ?? 80} now={now} onChanged={() => void reload()} />)}
            </div>
          )}
        </section>
      ))}
      {data && <DefaultCard d={data.default} now={now} />}
      {!lics.length && data && <div className="panel empty">Aún no hay licencias. <a href="#/licenses">Añade la primera</a> para ver su consumo aquí.</div>}
    </>
  );
}
