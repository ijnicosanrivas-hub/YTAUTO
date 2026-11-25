import { useEffect, useState } from "react";
import { api } from "../api";
import { Icon } from "../components/Icon";
import { ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import { creditsLeft, fmtCredits } from "../accounts";
import type { AccountsView, HiggsView } from "../types";

/** Barra de créditos restantes (verde → ámbar → rojo según lo que queda). */
function CreditMeter({ left, total, label }: { left: number | null; total: number | null; label: string }) {
  const pct = left != null && total ? Math.max(0, Math.min(100, (left / total) * 100)) : null;
  const color = pct == null ? "var(--muted)" : pct < 10 ? "var(--danger)" : pct < 30 ? "var(--warn)" : "var(--ok)";
  return (
    <div className="acc-meter">
      <div className="acc-big"><b>{fmtCredits(left)}</b><span className="muted">{label}{total ? ` de ${fmtCredits(total)}` : ""}</span></div>
      <div className="meter" aria-label={label}><i style={{ width: `${pct ?? 0}%`, background: color }} /></div>
    </div>
  );
}

function Step({ n, done, title, children }: { n: number; done: boolean; title: string; children?: React.ReactNode }) {
  return (
    <div className={`acc-step ${done ? "done" : ""}`}>
      <span className="acc-step-n">{done ? <Icon name="check" size={14} /> : n}</span>
      <div><b>{title}</b>{children && <div className="acc-step-body">{children}</div>}</div>
    </div>
  );
}

function AlwaysToggle({ pid, on, onChanged }: { pid: string; on: boolean; onChanged: () => void }) {
  const { busy, error, run } = useAction();
  return (
    <label className="acc-always">
      <input type="checkbox" checked={on} disabled={busy} onChange={async (e) => {
        if (e.target.checked && !confirm("Con esto, TODOS los vídeos podrán gastar créditos de esta cuenta sin preguntarte. ¿Seguro?")) return;
        if (await run(() => api.put(`/api/accounts/${pid}/always`, { authorized: e.target.checked }))) onChanged();
      }} />
      <span>Autorizar en todos los vídeos <small className="muted">(si no, lo marcas en cada vídeo nuevo)</small></span>
      <ErrorBox error={error} />
    </label>
  );
}

function ElevenCard({ v, onChanged }: { v: AccountsView["elevenlabs"]; onChanged: () => void }) {
  const { busy, error, run } = useAction();
  const plan = v.plans.creator;
  const [key, setKey] = useState("");
  const [price, setPrice] = useState(String(plan?.price_eur ?? ""));
  const [credits, setCredits] = useState(String(plan?.credits ?? ""));
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([]);
  const sub = v.subscription;
  useEffect(() => {
    if (!v.has_key) return;
    api.get<{ id: string; name: string }[]>("/api/accounts/elevenlabs/voices").then(setVoices).catch(() => setVoices([]));
  }, [v.has_key]);
  const save = (body: Record<string, unknown>) => run(() => api.post("/api/accounts/elevenlabs", body)).then((r) => { if (r) { setKey(""); onChanged(); } });
  return (
    <div className="panel acc-card" style={{ ["--acc" as string]: "#f5f5f5" }}>
      <div className="acc-head">
        <span className="acc-logo eleven" aria-hidden>11</span>
        <div>
          <h3>ElevenLabs <small className="muted">· voz</small></h3>
          <div className="muted small">{v.linked ? `Plan ${sub?.tier ?? "—"} · clave ${v.key_hint ?? ""}` : "Sin vincular"}</div>
        </div>
        <span className="spacer" />
        <span className={`badge ${v.linked && !v.error ? "s-completed" : v.error ? "s-error" : "s-paused"}`}>
          {v.linked ? (v.error ? "Revisar" : v.role === "primary" ? "Voz principal" : "Vinculada") : "No vinculada"}
        </span>
      </div>
      <ErrorBox error={error ?? v.error ?? null} />
      {sub && (
        <>
          <CreditMeter left={sub.remaining} total={sub.limit} label="créditos libres este ciclo" />
          <div className="lic-stats">
            <div><small>Gastados</small><b>{fmtCredits(sub.used)}</b></div>
            <div><small>Reinicio</small><b>{sub.resets_at_unix ? new Date(sub.resets_at_unix * 1000).toLocaleDateString("es-ES") : "—"}</b></div>
            <div><small>Uso comercial</small><b>{sub.commercial_use ? "Sí" : "No"}</b></div>
            <div><small>≈ locuciones de 60 s</small><b>{Math.floor(sub.remaining / 900)}</b></div>
          </div>
        </>
      )}
      <form className="acc-form" onSubmit={(e) => { e.preventDefault(); void save({ api_key: key || undefined, plan_price_eur: Number(price), plan_credits: Number(credits) }); }}>
        <label>Clave de API {v.has_key && <small className="muted">(déjala vacía para conservar la actual)</small>}
          <input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder={v.has_key ? "••••••••" : "sk_…  (elevenlabs.io → Developers → API Keys)"} />
        </label>
        <div className="acc-two">
          <label>Precio al mes (€)<input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
          <label>Créditos del plan<input type="number" min="1" value={credits} onChange={(e) => setCredits(e.target.value)} /></label>
        </div>
        {plan && <div className="muted small">Plan {plan.label}: {plan.note}. Se guarda para calcular el coste de cada locución.</div>}
        <button className="btn primary" disabled={busy || (!v.has_key && key.length < 10)}>{v.linked ? "Guardar" : "Vincular cuenta"}</button>
      </form>
      {v.linked && (
        <div className="acc-form">
          <div className="acc-two">
            <label>Voz del canal
              <select value={v.params?.default_voice_id ?? ""} onChange={(e) => void save({ voice_id: e.target.value })}>
                {voices.length === 0 && <option value={v.params?.default_voice_id ?? ""}>{v.params?.default_voice_id || "—"}</option>}
                {voices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </label>
            <label>Modelo
              <select value={v.params?.model_id ?? "eleven_multilingual_v2"} onChange={(e) => void save({ model_id: e.target.value })}>
                {Object.entries(v.models).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
          </div>
          <div className="muted small">Antes de cada locución se mira el saldo real: si no queda (más la reserva de {fmtCredits(v.params?.reserve_credits ?? 0)}), la voz pasa a la gratuita y nunca se cobra uso extra.</div>
          <AlwaysToggle pid="elevenlabs" on={v.always_authorized} onChanged={onChanged} />
          <div className="row">
            {v.role !== "primary" && <button className="btn" disabled={busy} onClick={() => void save({ primary: true })}>Usar como voz principal</button>}
            <span className="spacer" />
            <button className="btn danger" disabled={busy} onClick={async () => {
              if (!confirm("¿Desvincular ElevenLabs? Se borra la clave guardada.")) return;
              if (await run(() => api.del("/api/accounts/elevenlabs"))) onChanged();
            }}>Desvincular</button>
          </div>
        </div>
      )}
    </div>
  );
}

function HiggsCard({ v, onChanged }: { v: HiggsView; onChanged: () => void }) {
  const { busy, error, run } = useAction();
  const plan = v.plans.plus;
  const st = v.status;
  const [price, setPrice] = useState(String(plan?.price_eur ?? ""));
  const [credits, setCredits] = useState(String(plan?.credits ?? ""));
  const [login, setLogin] = useState<{ opened: boolean; command: string } | null>(null);
  const [estimate, setEstimate] = useState<{ credits: number; eur: number; detail: string } | null>(null);
  const linked = v.video.linked || v.image.linked;
  const save = (body: Record<string, unknown>) => run(() => api.post("/api/accounts/higgsfield", body)).then((r) => { if (r) onChanged(); });
  const left = creditsLeft(st.credits, v.reserve_credits);
  return (
    <div className="panel acc-card" style={{ ["--acc" as string]: "#c6f432" }}>
      <div className="acc-head">
        <span className="acc-logo higgs" aria-hidden>H</span>
        <div>
          <h3>Higgsfield <small className="muted">· vídeo e imagen</small></h3>
          <div className="muted small">{st.logged_in ? `Sesión iniciada${st.plan ? ` · plan ${st.plan}` : ""}` : st.installed ? "CLI instalada · falta iniciar sesión" : "Sin instalar"}</div>
        </div>
        <span className="spacer" />
        <span className={`badge ${linked && st.logged_in ? "s-completed" : st.logged_in ? "s-active" : "s-paused"}`}>
          {linked && st.logged_in ? "Conectada" : st.logged_in ? "Lista para activar" : "No conectada"}
        </span>
      </div>
      <ErrorBox error={error} />
      <div className="acc-note">
        <Icon name="alert" size={16} />
        <span>Los créditos de tu plan <b>solo</b> se pueden usar a través de la <b>CLI oficial</b> de Higgsfield (la API es otro producto con saldo aparte en dólares). Por eso YTAUTO usa la CLI con tu sesión: gasta los mismos créditos que la web, a tarifa estándar (lo «Unlimited» solo vale en la web). <a href={v.help.api} target="_blank" rel="noreferrer">Fuente oficial</a></span>
      </div>
      {st.logged_in && <CreditMeter left={st.credits} total={plan?.credits ?? null} label="créditos del plan" />}
      <div className="acc-steps">
        <Step n={1} done={!!st.installed} title="Instalar la CLI oficial">
          {!st.installed && (
            <>
              <div className="muted small">Se descarga la versión publicada por Higgsfield y se comprueba su huella SHA-256 antes de instalarla (sin Node ni administrador).</div>
              <button className="btn primary" disabled={busy} onClick={async () => { if (await run(() => api.post("/api/accounts/higgsfield/install"))) onChanged(); }}>
                {busy ? "Instalando…" : "Instalar Higgsfield"}
              </button>
            </>
          )}
          {st.installed && <div className="muted small mono">{v.cli_path}</div>}
        </Step>
        <Step n={2} done={!!st.logged_in} title="Iniciar sesión con tu cuenta">
          {st.installed && !st.logged_in && (
            <>
              <div className="muted small">Se abre una ventana en este PC: entra con tu cuenta de higgsfield.ai y vuelve aquí.</div>
              <div className="row">
                <button className="btn primary" disabled={busy} onClick={async () => { const r = await run(() => api.post<{ opened: boolean; command: string }>("/api/accounts/higgsfield/login")); if (r) setLogin(r); }}>Iniciar sesión</button>
                <button className="btn" onClick={() => onChanged()}>Ya he entrado</button>
              </div>
              {login && !login.opened && <div className="muted small">Abre una terminal y escribe: <code className="mono copy">{login.command}</code></div>}
            </>
          )}
        </Step>
        <Step n={3} done={linked} title="Elegir qué hará Higgsfield">
          {st.logged_in && (
            <div className="acc-form">
              <div className="acc-two">
                <label>Precio del plan al mes (€)<input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
                <label>Créditos al mes<input type="number" min="1" value={credits} onChange={(e) => setCredits(e.target.value)} /></label>
              </div>
              <div className="acc-uses">
                <label className="acc-use">
                  <input type="checkbox" checked={v.video.linked} disabled={busy} onChange={(e) => void save({ use_video: e.target.checked, plan_price_eur: Number(price), plan_credits: Number(credits), max_clips_per_video: v.video.max_per_video ?? 3 })} />
                  <span><b>Clips de vídeo</b><small className="muted">escenas en movimiento</small></span>
                </label>
                <label className="acc-use">
                  <input type="checkbox" checked={v.image.linked} disabled={busy} onChange={(e) => void save({ use_image: e.target.checked, plan_price_eur: Number(price), plan_credits: Number(credits), max_images_per_video: v.image.max_per_video ?? 8 })} />
                  <span><b>Imágenes</b><small className="muted">fondos y planos fijos</small></span>
                </label>
              </div>
              {v.video.linked && (
                <div className="acc-two">
                  <label>Modelo de vídeo
                    <select value={v.video.model ?? ""} onChange={(e) => void save({ video_model: e.target.value })}>
                      {Object.entries(v.video_models).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </label>
                  <label>Resolución
                    <select value={v.video.resolution ?? "720p"} onChange={(e) => void save({ resolution: e.target.value })}>
                      <option value="480p">480p · el más barato</option><option value="720p">720p · equilibrado</option><option value="1080p">1080p · máxima nitidez</option>
                    </select>
                  </label>
                  <label>Máx. clips por vídeo<input type="number" min="0" max="40" defaultValue={v.video.max_per_video ?? 3} onBlur={(e) => void save({ max_clips_per_video: Number(e.target.value) })} /></label>
                </div>
              )}
              {v.image.linked && (
                <div className="acc-two">
                  <label>Modelo de imagen
                    <select value={v.image.model ?? ""} onChange={(e) => void save({ image_model: e.target.value })}>
                      {Object.entries(v.image_models).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </label>
                  <label>Máx. imágenes por vídeo<input type="number" min="0" max="60" defaultValue={v.image.max_per_video ?? 8} onBlur={(e) => void save({ max_images_per_video: Number(e.target.value) })} /></label>
                </div>
              )}
              {v.video.linked && (
                <div className="row">
                  <button className="btn" type="button" disabled={busy} onClick={async () => { const r = await run(() => api.post<{ credits: number; eur: number; detail: string }>("/api/accounts/higgsfield/estimate?kind=video&seconds=5")); if (r) setEstimate(r); }}>¿Cuánto cuesta un clip de 5 s?</button>
                  {estimate && <span className="small">{fmtCredits(estimate.credits)} créditos ≈ {estimate.eur.toFixed(2)} € <span className="muted">({estimate.detail})</span></span>}
                </div>
              )}
              {left != null && <div className="muted small">Reserva intocable: {fmtCredits(v.reserve_credits ?? 0)} créditos. Antes de cada clip se mira tu saldo y, si no llega, la escena usa imagen gratuita.</div>}
            </div>
          )}
        </Step>
      </div>
      {linked && (
        <>
          <AlwaysToggle pid="higgsfield_video" on={v.always_authorized.higgsfield_video} onChanged={onChanged} />
          <div className="row">
            <span className="spacer" />
            <button className="btn danger" disabled={busy} onClick={async () => {
              if (!confirm("¿Desconectar Higgsfield de YTAUTO? Tu cuenta y tu sesión no se tocan.")) return;
              if (await run(() => api.del("/api/accounts/higgsfield"))) onChanged();
            }}>Desconectar</button>
          </div>
        </>
      )}
    </div>
  );
}

export default function Accounts() {
  const { data, error, reload } = useApi<AccountsView>("/api/accounts", { pollMs: 60000 });
  const refresh = () => void api.get<AccountsView>("/api/accounts?refresh=true").then(() => reload());
  return (
    <div>
      <PageHead title="Cuentas conectadas" subtitle="Vincula tus suscripciones de voz y vídeo. Las claves se guardan cifradas en este PC y nunca se gasta nada sin tu autorización.">
        <button className="btn" onClick={refresh}><Icon name="history" size={16} /> Actualizar saldos</button>
      </PageHead>
      <ErrorBox error={error} />
      {!data && !error && <div className="empty">Cargando cuentas…</div>}
      {data && (
        <div className="acc-grid">
          <ElevenCard v={data.elevenlabs} onChanged={reload} />
          <HiggsCard v={data.higgsfield} onChanged={reload} />
        </div>
      )}
    </div>
  );
}
