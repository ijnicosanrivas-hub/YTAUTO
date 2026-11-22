import { withChannel } from "../channels";
import { Badge, ErrorBox, PageHead, Progress, useApi } from "../components/ui";
import { shortDate, statusLabel } from "../format";
import { useLive } from "../store";
import type { ProjectSummary } from "../types";

export default function Projects() {
  const channel = useLive((s) => s.channel);
  const { data, error } = useApi<ProjectSummary[]>(withChannel("/api/projects", channel), { live: true });
  return (
    <>
      <PageHead title="Proyectos" subtitle="Producciones de este canal, su avance real y lo que espera tu aprobación">
        <a className="btn primary" href="#/new">+ Nuevo vídeo</a>
      </PageHead>
      <ErrorBox error={error} />
      <div className="panel" style={{ marginTop: 14 }}>
        {data?.length ? (
          <table>
            <thead>
              <tr>
                <th>Proyecto</th>
                <th>Duración</th>
                <th>Avance</th>
                <th>Siguiente fase</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className="clickable" onClick={() => (location.hash = `#/projects/${p.id}`)}>
                  <td>
                    {p.name}
                    <div className="muted">{p.topic}</div>
                  </td>
                  <td>{p.duration_s} s</td>
                  <td style={{ width: 160 }}>
                    <Progress value={p.progress} />
                    <span className="muted mono">{Math.round(p.progress * 100)}%</span>
                  </td>
                  <td>
                    {p.waiting_approval.length ? <Badge status="in_review" label={`Aprobar: ${p.waiting_approval.join(", ")}`} /> : p.next_phase ?? "—"}
                    {p.blocked_reason && <div className="muted">{p.blocked_reason}</div>}
                  </td>
                  <td>
                    <Badge status={p.status} />
                    <div className="muted mono">{shortDate(p.created_at)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No hay proyectos. Crea el primero con «Nuevo vídeo».</div>
        )}
      </div>
      <p className="muted">Estados: {["pending", "running", "blocked", "completed", "error", "in_review", "approved"].map(statusLabel).join(" · ")}</p>
    </>
  );
}
