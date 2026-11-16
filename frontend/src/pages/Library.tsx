import { useState } from "react";
import { fileUrl } from "../api";
import { PageHead, useApi } from "../components/ui";

interface LibAsset {
  project_id: string;
  project: string;
  scene: number;
  kind: string;
  provider: string;
  license: { name: string; attribution?: string; url?: string } | null;
  prompt: string | null;
  width: number | null;
  height: number | null;
  file: string | null;
}

export default function Library() {
  const { data } = useApi<{ assets: LibAsset[] }>("/api/library", { live: true });
  const [q, setQ] = useState("");
  const items = (data?.assets ?? []).filter((a) => !q || `${a.project} ${a.prompt} ${a.provider} ${a.license?.name}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHead title="Biblioteca de recursos" subtitle="Recursos generados o reutilizados, con procedencia y licencia">
        <input placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} />
      </PageHead>
      <div className="panel">
        <p className="muted">
          Para añadir tus propios recursos con licencia, colócalos en <span className="mono">library/images|videos|music|sfx</span> con su
          ficha <span className="mono">.json</span> (licencia, autor, etiquetas). Los ficheros sin licencia se ignoran.
        </p>
        {items.length ? (
          <div className="thumbs">
            {items.map((a, i) => (
              <figure key={i} style={{ margin: 0 }}>
                {a.kind === "image" && a.file ? (
                  <img src={fileUrl(a.project_id, a.file)} alt={a.prompt ?? ""} loading="lazy" title={a.prompt ?? ""} />
                ) : (
                  <div className="empty">{a.kind}</div>
                )}
                <figcaption className="muted" style={{ fontSize: 11 }}>
                  {a.project} · #{a.scene}
                  <br />
                  {a.provider} · {a.license?.name ?? "?"}
                </figcaption>
              </figure>
            ))}
          </div>
        ) : (
          <div className="empty">Sin recursos todavía.</div>
        )}
      </div>
    </>
  );
}
