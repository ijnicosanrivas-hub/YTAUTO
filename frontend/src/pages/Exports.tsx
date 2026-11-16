import { useEffect, useState } from "react";
import { api, fileUrl } from "../api";
import { Badge, PageHead, useApi } from "../components/ui";
import { PLATFORM_LABEL } from "../format";
import type { ProjectSummary } from "../types";

interface Row {
  project: ProjectSummary;
  exports: Record<string, { path: string; duration_s: number; size_bytes: number }> | null;
  results: Record<string, { status: string; url?: string; message?: string }> | null;
}

export default function Exports() {
  const { data: projects } = useApi<ProjectSummary[]>("/api/projects", { live: true });
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    if (!projects) return;
    void Promise.all(
      projects.map(async (p) => {
        const a = await api.get<Record<string, unknown>>(`/api/projects/${p.id}/artifacts`);
        return { project: p, exports: a.exports as Row["exports"], results: a.publish_results as Row["results"] };
      }),
    ).then((r) => setRows(r.filter((x) => x.exports)));
  }, [projects]);

  return (
    <>
      <PageHead title="Exportaciones y publicaciones" subtitle="Un máster por vídeo y sus versiones por plataforma; publicación solo con autorización" />
      <div className="panel">
        {rows.length ? (
          <table>
            <thead><tr><th>Proyecto</th><th>Plataforma</th><th>Archivo</th><th>Publicación</th></tr></thead>
            <tbody>
              {rows.flatMap((r) =>
                Object.entries(r.exports ?? {}).map(([platform, e]) => {
                  const rel = e.path.split(`/${r.project.id}/`)[1];
                  const res = r.results?.[platform];
                  return (
                    <tr key={r.project.id + platform}>
                      <td><a href={`#/projects/${r.project.id}`}>{r.project.name}</a></td>
                      <td>{PLATFORM_LABEL[platform] ?? platform}</td>
                      <td className="mono"><a href={fileUrl(r.project.id, rel)} download>{platform}.mp4</a> · {e.duration_s.toFixed(1)} s · {(e.size_bytes / 1e6).toFixed(1)} MB</td>
                      <td>
                        {res ? <Badge status={res.status === "skipped" ? "pending" : res.status === "failed" ? "error" : "completed"} label={res.status} /> : <Badge status="pending" label="sin publicar" />}
                        {res?.url && <div><a href={res.url} target="_blank" rel="noreferrer">{res.url}</a></div>}
                        {res?.message && <div className="muted">{res.message}</div>}
                      </td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        ) : <div className="empty">Aún no hay exportaciones.</div>}
      </div>
    </>
  );
}
