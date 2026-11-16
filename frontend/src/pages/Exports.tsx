import { useEffect, useState } from "react";
import { api, fileUrl } from "../api";
import { Badge, PageHead, useApi } from "../components/ui";
import { PLATFORM_LABEL } from "../format";
import type { ExportValidation, PlatformProfile, ProjectSummary } from "../types";

interface Row {
  project: ProjectSummary;
  exports: Record<string, { path: string; duration_s: number; size_bytes: number; validation?: ExportValidation }> | null;
  results: Record<string, { status: string; url?: string; message?: string }> | null;
}

function Profiles() {
  const { data } = useApi<PlatformProfile[]>("/api/platforms");
  if (!data) return null;
  return (
    <div className="grid cols-3" style={{ marginBottom: 14 }}>
      {data.map((p) => (
        <div key={p.id} className="panel">
          <div className="row">
            <b>{p.display_name}</b>
            <span className="spacer" />
            {p.is_verified ? <Badge status="completed" label={`Verificado ${p.verified_at}`} /> : <Badge status="blocked" label="Sin verificar" />}
          </div>
          <p className="mono muted" style={{ margin: "8px 0" }}>
            {p.encode.width}×{p.encode.height} · {p.encode.fps} fps · {p.min_duration_s}–{p.max_duration_s} s · {p.file.containers.join("/")}
            {p.file.max_size_mb ? ` · ≤${p.file.max_size_mb} MB` : ""}
            {p.file.fps_min ? ` · ${p.file.fps_min}–${p.file.fps_max} fps` : ""}
          </p>
          <p className="muted">
            Texto: {p.metadata.mode === "title_description" ? `título ≤${p.metadata.title_max_chars}, descripción ≤${p.metadata.description_max_bytes} bytes` : `pie ≤${p.metadata.caption_max} · hashtags ≤${p.metadata.hashtags_max}`}
          </p>
          {p.publish.notes.length > 0 && (
            <ul style={{ margin: "6px 0", paddingLeft: 18 }}>{p.publish.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          )}
          {p.unverified.length > 0 && <p style={{ color: "var(--warn)" }}>No verificado oficialmente: {p.unverified.join(", ")}</p>}
          <div className="row" style={{ fontSize: 12 }}>
            {p.sources.map((u, i) => <a key={u} href={u} target="_blank" rel="noreferrer">fuente {i + 1}</a>)}
          </div>
        </div>
      ))}
    </div>
  );
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
      <Profiles />
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
                      <td className="mono"><a href={fileUrl(r.project.id, rel)} download>{platform}.mp4</a> · {e.duration_s.toFixed(1)} s · {(e.size_bytes / 1e6).toFixed(1)} MB
                        {e.validation && <div>{e.validation.ok ? <Badge status="completed" label={`${e.validation.checked.length} comprobaciones OK`} /> : <Badge status="error" label="No válido" />}</div>}
                        {e.validation?.issues.map((i) => <div key={i.code} className="muted">{i.severity === "error" ? "✖" : "⚠"} {i.message}</div>)}
                      </td>
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
