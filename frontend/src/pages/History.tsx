import { useState } from "react";
import { PageHead, useApi } from "../components/ui";
import { describeEvent } from "../format";
import type { YtEvent } from "../types";

export default function History() {
  const { data } = useApi<(YtEvent & { id: number })[]>("/api/events?limit=1000", { live: true });
  const [type, setType] = useState("");
  const types = Array.from(new Set((data ?? []).map((e) => e.type))).sort();
  const items = [...(data ?? [])].reverse().filter((e) => !type || e.type === type);
  return (
    <>
      <PageHead title="Historial" subtitle="Registro persistente de todo lo ocurrido en la fábrica">
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Todos los eventos</option>
          {types.map((t) => <option key={t}>{t}</option>)}
        </select>
      </PageHead>
      <div className="panel">
        <table>
          <thead><tr><th>Fecha</th><th>Proyecto</th><th>Agente / fase</th><th>Evento</th></tr></thead>
          <tbody>
            {items.slice(0, 500).map((e) => (
              <tr key={e.id}>
                <td className="mono">{new Date(e.at).toLocaleString("es-ES")}</td>
                <td className="mono">{e.project_id ? <a href={`#/projects/${e.project_id}`}>{e.project_id}</a> : "—"}</td>
                <td>{e.agent ?? e.phase ?? "sistema"}</td>
                <td>{describeEvent(e.type, e.data)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && <div className="empty">Sin eventos.</div>}
      </div>
    </>
  );
}
