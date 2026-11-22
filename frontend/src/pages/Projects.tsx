import { useState } from "react";
import { withChannel } from "../channels";
import { ChannelArt } from "../components/ChannelArt";
import { Icon } from "../components/Icon";
import { Badge, ErrorBox, PageHead, Progress, useApi } from "../components/ui";
import { shortDate } from "../format";
import { useLive } from "../store";
import type { Channel, ProjectSummary } from "../types";

const FILTERS: [string, string][] = [["all", "Todos"], ["active", "En curso"], ["waiting", "Esperan decisión"], ["completed", "Terminados"], ["blocked", "Bloqueados"]];

export default function Projects() {
  const channel = useLive((s) => s.channel);
  const { data, error } = useApi<ProjectSummary[]>(withChannel("/api/projects", channel), { live: true });
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const profile = channels?.find((c) => c.id === channel)?.theme ?? "gotham";
  const [filter, setFilter] = useState("all");
  const list = (data ?? []).filter((p) => filter === "all" || (filter === "waiting" ? p.waiting_approval.length > 0 : p.status === filter));
  return (
    <>
      <PageHead title="Proyectos" subtitle="Las producciones de este canal, su avance real y lo que espera tu aprobación" />
      <div className="tabs" role="tablist">
        {FILTERS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={filter === k} className={`tab ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)}>
            {label}{data ? ` · ${k === "all" ? data.length : data.filter((p) => (k === "waiting" ? p.waiting_approval.length > 0 : p.status === k)).length}` : ""}
          </button>
        ))}
      </div>
      <ErrorBox error={error} />
      {list.length ? (
        <div className="project-grid">
          {list.map((p) => (
            <article key={p.id} className="project-card" onClick={() => (location.hash = `#/projects/${p.id}`)} tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter") location.hash = `#/projects/${p.id}`; }}>
              <div className="project-thumb">
                <ChannelArt profile={profile} />
                <Badge status={p.waiting_approval.length ? "in_review" : p.status} label={p.waiting_approval.length ? "Espera tu decisión" : undefined} />
                <span className="vertical"><Icon name="play" size={18} /></span>
              </div>
              <div className="project-body">
                <b>{p.name}</b>
                <div className="project-meta"><span>{p.duration_s} s · 9:16</span><span>{shortDate(p.created_at)}</span></div>
                <Progress value={p.progress} />
                <div className="project-meta">
                  <span>{Math.round(p.progress * 100)} % completado</span>
                  <span>{p.waiting_approval.length ? `Aprobar: ${p.waiting_approval.join(", ")}` : p.next_phase ? `Siguiente: ${p.next_phase}` : "—"}</span>
                </div>
                {p.blocked_reason && <div className="alert err small" style={{ margin: 0 }}>{p.blocked_reason}</div>}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="panel empty">
          {data?.length ? "Ningún proyecto con este filtro." : <>Este canal aún no tiene proyectos. <a href="#/new">Crea el primer vídeo</a></>}
        </div>
      )}
    </>
  );
}
