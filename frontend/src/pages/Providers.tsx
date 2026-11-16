import { useState } from "react";
import { api } from "../api";
import { Badge, ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import { CATEGORY_LABEL } from "../format";
import type { AdapterInfo, ProviderView } from "../types";

interface TestReport {
  passed: boolean;
  skipped: string | null;
  checks: { name: string; passed: boolean; detail: string }[];
}

function ProviderRow({ p, siblings, onChange }: { p: ProviderView; siblings: ProviderView[]; onChange: () => void }) {
  const [key, setKey] = useState(p.required_credentials[0] ?? "api_key");
  const [secret, setSecret] = useState("");
  const [report, setReport] = useState<TestReport | null>(null);
  const [params, setParams] = useState(JSON.stringify(p.params));
  const [budget, setBudget] = useState(p.monthly_budget_eur?.toString() ?? "");
  const { busy, error, run } = useAction();
  const done = async (fn: () => Promise<unknown>) => {
    await run(fn);
    onChange();
  };
  const order = (first: string) => [first, ...siblings.map((s) => s.id).filter((i) => i !== first)];

  return (
    <tr>
      <td>
        <b>{p.display_name}</b>
        <div className="muted mono">{p.id} · {p.adapter}</div>
        <div className="row" style={{ marginTop: 4 }}>
          <Badge status={p.role} label={p.role === "primary" ? "Principal" : p.role === "fallback" ? "Alternativo" : "Desactivado"} />
          {p.is_paid ? <Badge status="blocked" label="De pago" /> : <Badge status="completed" label="Gratuito" />}
          {p.is_local && <Badge status="idle" label="Local" />}
          {p.requires_network && <Badge status="in_review" label="Servicio externo" />}
        </div>
      </td>
      <td style={{ minWidth: 230 }}>
        {p.status.healthy == null ? <span className="muted">Sin probar</span> : p.status.healthy ? <Badge status="completed" label="Disponible" /> : <Badge status="error" label="No disponible" />}
        <div className="muted" style={{ fontSize: 12 }}>{p.status.message}</div>
        {p.status.last_error && <div style={{ color: "var(--danger)", fontSize: 12 }}>Último error: {p.status.last_error.slice(0, 120)}</div>}
        <div className="muted mono">✔ {p.status.success_count} · ✖ {p.status.error_count}</div>
        {report && (
          <div style={{ fontSize: 12, marginTop: 6 }}>
            {report.skipped ? <span className="muted">{report.skipped}</span> : report.checks.map((c) => (
              <div key={c.name}>{c.passed ? "✅" : "❌"} {c.name} <span className="muted">{c.detail}</span></div>
            ))}
          </div>
        )}
      </td>
      <td style={{ minWidth: 250 }}>
        {p.required_credentials.length > 0 ? (
          <>
            {Object.entries(p.credentials).map(([k, hint]) => (
              <div key={k} className="mono">{k}: {hint}</div>
            ))}
            {p.missing_credentials.length > 0 && <div style={{ color: "var(--warn)" }}>Faltan: {p.missing_credentials.join(", ")}</div>}
            <div className="row" style={{ marginTop: 4 }}>
              <select value={key} onChange={(e) => setKey(e.target.value)}>
                {p.required_credentials.map((k) => <option key={k}>{k}</option>)}
              </select>
              <input type="password" autoComplete="off" placeholder="Nueva clave" value={secret} onChange={(e) => setSecret(e.target.value)} style={{ width: 130 }} />
              <button className="btn" disabled={busy || !secret} onClick={() => done(async () => { await api.put(`/api/providers/${p.id}/credentials`, { key, value: secret }); setSecret(""); })}>Guardar</button>
            </div>
          </>
        ) : <span className="muted">No requiere credenciales</span>}
      </td>
      <td style={{ minWidth: 220 }}>
        <label className="field">Parámetros (JSON)
          <input className="mono" value={params} onChange={(e) => setParams(e.target.value)} />
        </label>
        {p.is_paid && (
          <label className="field">Presupuesto mensual (€)
            <input type="number" min={0} value={budget} onChange={(e) => setBudget(e.target.value)} />
          </label>
        )}
        <button className="btn" style={{ marginTop: 4 }} disabled={busy} onClick={() => done(() => api.patch(`/api/providers/${p.id}`, {
          params: JSON.parse(params || "{}"), ...(p.is_paid ? { monthly_budget_eur: budget === "" ? null : Number(budget) } : {}),
        }))}>Aplicar</button>
      </td>
      <td>
        <div className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
          <button className="btn" disabled={busy} onClick={() => run(async () => { setReport(await api.post<TestReport>(`/api/providers/${p.id}/test`)); onChange(); })}>Probar conexión</button>
          {p.role !== "primary" && <button className="btn" disabled={busy} onClick={() => done(() => api.post("/api/providers/order", { category: p.category, ids: order(p.id) }))}>Hacer principal</button>}
          <button className="btn" disabled={busy} onClick={() => done(() => api.patch(`/api/providers/${p.id}`, { enabled: !p.enabled }))}>{p.enabled ? "Desactivar" : "Activar"}</button>
          <button className="btn danger" disabled={busy} onClick={() => confirm(`¿Eliminar ${p.display_name}?`) && done(() => api.del(`/api/providers/${p.id}`))}>Eliminar</button>
        </div>
        <ErrorBox error={error} />
      </td>
    </tr>
  );
}

export default function Providers() {
  const { data, reload } = useApi<{ providers: ProviderView[]; categories: string[] }>("/api/providers");
  const { data: catalog } = useApi<AdapterInfo[]>("/api/providers/catalog");
  const [adapter, setAdapter] = useState("");
  const [newId, setNewId] = useState("");
  const { busy, error, run } = useAction();
  const byCat = (cat: string) => (data?.providers ?? []).filter((p) => p.category === cat);

  return (
    <>
      <PageHead title="Configuración de proveedores" subtitle="Cambia de proveedor sin tocar el código: añade, prueba, ordena y selecciona el principal" />
      <div className="panel" style={{ marginBottom: 14 }}>
        <h2>Añadir proveedor</h2>
        <ErrorBox error={error} />
        <div className="row">
          <select value={adapter} onChange={(e) => setAdapter(e.target.value)}>
            <option value="">Elige un adaptador instalado…</option>
            {(data?.categories ?? []).map((cat) => (
              <optgroup key={cat} label={CATEGORY_LABEL[cat] ?? cat}>
                {catalog?.filter((a) => a.category === cat).map((a) => (
                  <option key={a.name} value={a.name}>{a.display_name}{a.is_paid ? " (de pago)" : ""}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <input placeholder="Identificador (opcional)" value={newId} onChange={(e) => setNewId(e.target.value)} />
          <button className="btn primary" disabled={busy || !adapter} onClick={async () => {
            await run(() => api.post("/api/providers", { adapter, id: newId || undefined }));
            setAdapter(""); setNewId(""); void reload();
          }}>Añadir</button>
        </div>
        {adapter && <p className="muted">{catalog?.find((a) => a.name === adapter)?.doc}</p>}
        <p className="muted">Los proveedores de pago solo se usan con presupuesto y autorización expresa; el sistema nunca cambia a uno de pago por su cuenta.</p>
      </div>
      {(data?.categories ?? []).map((cat) => (
        <div key={cat} className="panel" style={{ marginBottom: 14, overflowX: "auto" }}>
          <h2>{CATEGORY_LABEL[cat] ?? cat}</h2>
          {byCat(cat).length ? (
            <table>
              <thead><tr><th>Proveedor</th><th>Estado</th><th>Credenciales</th><th>Configuración</th><th>Acciones</th></tr></thead>
              <tbody>{byCat(cat).map((p) => <ProviderRow key={p.id + p.priority} p={p} siblings={byCat(cat)} onChange={reload} />)}</tbody>
            </table>
          ) : <div className="empty">Sin proveedores en esta categoría.</div>}
        </div>
      ))}
    </>
  );
}
