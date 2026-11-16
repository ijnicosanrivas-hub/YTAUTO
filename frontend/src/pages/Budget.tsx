import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageHead, Progress, useAction, useApi } from "../components/ui";
import { eur, shortDate } from "../format";

interface BudgetData {
  summary: { month: string; spent_month_eur: number; monthly_budget_eur: number | null; by_provider: { provider_id: string; month: string; operations: number; eur: number }[] } | null;
  ledger: { id: number; project_id: string | null; provider_id: string; operation: string; amount_eur: number; status: string; at: string; scene_index: number | null }[];
  warn_fraction: number;
  spend_authorized_providers: string[];
}

export default function Budget() {
  const { data, reload } = useApi<BudgetData>("/api/budget", { live: true });
  const [monthly, setMonthly] = useState("");
  const [warn, setWarn] = useState("80");
  const { busy, error, run } = useAction();
  useEffect(() => {
    if (data) {
      setMonthly(data.summary?.monthly_budget_eur?.toString() ?? "");
      setWarn(String(Math.round(data.warn_fraction * 100)));
    }
  }, [data]);
  const s = data?.summary;
  const pct = s?.monthly_budget_eur ? s.spent_month_eur / s.monthly_budget_eur : 0;

  return (
    <>
      <PageHead title="Presupuesto" subtitle="Gasto en proveedores externos. La licencia Claude Pro no se factura por uso y no aparece aquí." />
      <div className="grid cols-3">
        <div className="panel">
          <h2>Gasto este mes ({s?.month})</h2>
          <div className="kpi">{eur(s?.spent_month_eur ?? 0)}<small>{s?.monthly_budget_eur != null ? `de ${eur(s.monthly_budget_eur)}` : "sin límite mensual"}</small></div>
          {s?.monthly_budget_eur ? <Progress value={Math.min(1, pct)} /> : null}
        </div>
        <div className="panel">
          <h2>Límites</h2>
          <ErrorBox error={error} />
          <label className="field">Presupuesto mensual global (€, vacío = sin límite)
            <input type="number" min={0} step={1} value={monthly} onChange={(e) => setMonthly(e.target.value)} />
          </label>
          <label className="field" style={{ marginTop: 8 }}>Avisar al alcanzar (%)
            <input type="number" min={10} max={100} value={warn} onChange={(e) => setWarn(e.target.value)} />
          </label>
          <button className="btn primary" style={{ marginTop: 10 }} disabled={busy} onClick={async () => {
            await run(() => api.put("/api/budget", { monthly_budget_eur: monthly === "" ? null : Number(monthly), warn_fraction: Number(warn) / 100 }));
            void reload();
          }}>Guardar</button>
          <p className="muted">El presupuesto por vídeo se fija al crear cada proyecto; el de cada proveedor, en «Proveedores».</p>
        </div>
        <div className="panel">
          <h2>Por proveedor</h2>
          {s?.by_provider.length ? (
            <table><tbody>{s.by_provider.map((p) => <tr key={p.provider_id + p.month}><td>{p.provider_id}</td><td className="mono">{p.month}</td><td>{p.operations} op.</td><td>{eur(p.eur)}</td></tr>)}</tbody></table>
          ) : <div className="empty">Sin gasto registrado: todo es local/gratuito.</div>}
        </div>
      </div>
      <div className="panel" style={{ marginTop: 14 }}>
        <h2>Registro de consumo</h2>
        {data?.ledger.length ? (
          <table>
            <thead><tr><th>Fecha</th><th>Proyecto</th><th>Proveedor</th><th>Operación</th><th>Escena</th><th>Importe</th><th>Estado</th></tr></thead>
            <tbody>{[...data.ledger].reverse().map((l) => (
              <tr key={l.id}><td className="mono">{shortDate(l.at)}</td><td className="mono">{l.project_id}</td><td>{l.provider_id}</td><td>{l.operation}</td><td>{l.scene_index ?? "—"}</td><td>{eur(l.amount_eur)}</td><td>{l.status}</td></tr>
            ))}</tbody>
          </table>
        ) : <div className="empty">No hay operaciones de pago.</div>}
      </div>
    </>
  );
}
