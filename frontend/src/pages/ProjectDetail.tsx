import { useState } from "react";
import { api, fileUrl } from "../api";
import { Badge, ErrorBox, PageHead, Progress, useAction, useApi } from "../components/ui";
import { PLATFORM_LABEL, describeEvent, eur, statusLabel } from "../format";
import type { ProjectView, ProviderView, YtEvent } from "../types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Artifacts = Record<string, any>;

export default function ProjectDetail({ id }: { id: string }) {
  const { data: view, error, reload } = useApi<ProjectView>(`/api/projects/${id}`, { live: true });
  const { data: arts, reload: reloadArts } = useApi<Artifacts>(`/api/projects/${id}/artifacts`, { live: true });
  const [tab, setTab] = useState("phases");
  const act = useAction();

  if (error) return <ErrorBox error={error} />;
  if (!view) return <div className="empty">Cargando…</div>;
  const p = view.project;
  const control = async (action: string) => {
    await act.run(() => api.post(`/api/projects/${id}/${action}`));
    void reload();
  };

  return (
    <>
      <PageHead title={p.spec.name} subtitle={`${p.spec.topic} · ${p.spec.duration_s} s · ${p.spec.platforms.map((x) => PLATFORM_LABEL[x]).join(", ")}`}>
        <Badge status={p.status} />
        {p.status === "active" && <button className="btn" onClick={() => control("pause")}>Pausar</button>}
        {["paused", "blocked", "error"].includes(p.status) && <button className="btn" onClick={() => control("resume")}>Reanudar</button>}
        {!["cancelled", "completed"].includes(p.status) && (
          <button className="btn danger" onClick={() => confirm("¿Cancelar la producción?") && control("cancel")}>Cancelar</button>
        )}
      </PageHead>
      <ErrorBox error={act.error} />
      {p.blocked_reason && <div className={`alert ${p.status === "error" ? "err" : ""}`}>{p.blocked_reason}</div>}
      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="row">
          <span className="muted">Avance</span>
          <div style={{ flex: 1 }}>
            <Progress value={view.progress} />
          </div>
          <span className="mono">{Math.round(view.progress * 100)}%</span>
        </div>
      </div>

      <ApprovalPanel view={view} arts={arts} onDone={() => { void reload(); void reloadArts(); }} />

      <div className="tabs">
        {[["phases", "Fases"], ["script", "Guion"], ["plan", "Plan creativo"], ["video", "Vídeo"], ["review", "Revisión"],
          ["exports", "Exportaciones"], ["activity", "Actividad"]].map(([k, l]) => (
          <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "phases" && <Phases view={view} onChange={reload} />}
      {tab === "script" && <ScriptView arts={arts} />}
      {tab === "plan" && <PlanView arts={arts} />}
      {tab === "video" && <VideoView id={id} arts={arts} onChange={reload} />}
      {tab === "review" && <ReviewView arts={arts} />}
      {tab === "exports" && <ExportsView id={id} arts={arts} />}
      {tab === "activity" && <Activity id={id} view={view} />}
    </>
  );
}

function ApprovalPanel({ view, arts, onDone }: { view: ProjectView; arts: Artifacts | null; onDone: () => void }) {
  const id = view.project.id;
  const [note, setNote] = useState("");
  const { busy, error, run } = useAction();
  const { data: providers } = useApi<{ providers: ProviderView[] }>("/api/providers");
  const blockedSpend = view.phases.find((ph) => ph.status === "blocked" && ["spend_not_authorized", "budget_exceeded"].includes(ph.blocked_code ?? ""));
  const approve = async (gate: string, approved = true) => {
    await run(() => api.post(`/api/projects/${id}/approve`, { gate, approved, note }));
    setNote("");
    onDone();
  };
  if (!view.waiting_approval.length && !blockedSpend) return null;
  const pkg = arts?.publish_package as Record<string, { title: string; description: string; hashtags: string[] }> | null;

  return (
    <div className="panel" style={{ borderColor: "var(--warn)", marginBottom: 14 }}>
      <h2 style={{ color: "var(--warn)" }}>Panel de aprobación</h2>
      <ErrorBox error={error} />
      {view.waiting_approval.includes("script_approval") && (
        <>
          <p>El guion está listo. Revísalo en la pestaña «Guion». Si lo rechazas, el guionista lo reescribe con tu comentario.</p>
          <div className="row">
            <input style={{ flex: 1 }} placeholder="Comentario (obligatorio para rechazar)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn ok" disabled={busy} onClick={() => approve("script_approval")}>Aprobar guion</button>
            <button className="btn danger" disabled={busy || !note} onClick={() => approve("script_approval", false)}>Rechazar</button>
          </div>
        </>
      )}
      {view.waiting_approval.includes("final_approval") && (
        <>
          <p>
            Vídeo renderizado y revisado (calidad interna {arts?.review?.score ?? "—"}/100{arts?.review?.passed === false ? ", con observaciones" : ""}).
            Revísalo en «Vídeo» y «Revisión».
          </p>
          <div className="row">
            <input style={{ flex: 1 }} placeholder="Comentario (opcional)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn ok" disabled={busy} onClick={() => approve("final_approval")}>Aprobar y exportar</button>
            <button className="btn danger" disabled={busy} onClick={() => approve("final_approval", false)}>Rechazar</button>
          </div>
        </>
      )}
      {view.waiting_approval.includes("publish") && pkg && (
        <>
          <p>Material listo. Nada se publica sin tu autorización expresa (caduca a las 24 h). Por defecto se sube como privado.</p>
          <table>
            <tbody>
              {Object.entries(pkg).map(([platform, m]) => (
                <tr key={platform}>
                  <td>{PLATFORM_LABEL[platform] ?? platform}</td>
                  <td>
                    <b>{m.title}</b>
                    <div className="muted">{m.description}</div>
                    <div className="mono">{m.hashtags.join(" ")}</div>
                  </td>
                  <td>
                    <button className="btn ok" disabled={busy} onClick={() => approve(`publish:${platform}`)}>Autorizar publicación</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 10 }}>
            <span className="spacer" />
            <button className="btn" disabled={busy} onClick={() => approve("publish_decision")}>No publicar: lo haré manualmente</button>
          </div>
        </>
      )}
      {blockedSpend && (
        <>
          <p>
            <b>{statusLabel(blockedSpend.status)}:</b> {blockedSpend.error}
          </p>
          <div className="row">
            {providers?.providers.filter((pv) => pv.is_paid && pv.enabled).map((pv) => (
              <button key={pv.id} className="btn" disabled={busy} onClick={() => approve(`spend:${pv.id}`)}>
                Autorizar gasto en {pv.display_name}
              </button>
            ))}
            <a className="btn" href="#/providers">Configurar alternativa gratuita</a>
          </div>
        </>
      )}
    </div>
  );
}

function Phases({ view, onChange }: { view: ProjectView; onChange: () => void }) {
  const act = useAction();
  return (
    <div className="panel">
      <ErrorBox error={act.error} />
      <div className="phase-list">
        {view.phases.map((ph) => (
          <div key={ph.phase} className={`phase ${ph.status === "error" ? "err" : ""}`}>
            <span className="num">{String(ph.number).padStart(2, "0")}</span>
            <div style={{ minWidth: 0 }}>
              <div>
                {ph.title} <span className="muted">· {ph.agent ?? "aprobación"}{ph.attempts > 1 ? ` · ${ph.attempts} intentos` : ""}</span>
              </div>
              <div className="sum">{ph.error ?? ph.summary ?? ""}</div>
            </div>
            <div className="row">
              <Badge status={ph.status} />
              {["error", "blocked"].includes(ph.status) && ph.blocked_code !== "publish_authorization" && (
                <button className="btn" onClick={async () => { await act.run(() => api.post(`/api/projects/${view.project.id}/retry/${ph.phase}`)); onChange(); }}>
                  Reintentar
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScriptView({ arts }: { arts: Artifacts | null }) {
  const s = arts?.script;
  if (!s) return <div className="panel empty">El guion aún no está escrito.</div>;
  return (
    <div className="panel">
      <h2>{s.internal_title}</h2>
      <p><b>Objetivo:</b> {s.narrative_goal}</p>
      <p><b>Gancho:</b> {s.hook}</p>
      {s.scenes.map((sc: any) => (
        <div key={sc.index} className="script-scene">
          <div className="row">
            <span className="mono">#{sc.index}</span> <Badge status="pending" label={sc.section} />
            <span className="muted mono">{sc.duration_s.toFixed(1)} s · {sc.narration.split(" ").length} palabras</span>
          </div>
          <p style={{ margin: "6px 0" }}>{sc.narration}</p>
          <div className="muted">🎬 {sc.visual_notes}{sc.sfx?.length ? ` · 🔊 ${sc.sfx.join(", ")}` : ""}</div>
        </div>
      ))}
      <p><b>Cierre:</b> {s.closing}</p>
    </div>
  );
}

function PlanView({ arts }: { arts: Artifacts | null }) {
  const b = arts?.brief;
  if (!b) return <div className="panel empty">El plan creativo aún no existe.</div>;
  return (
    <div className="panel">
      <h2>Plan creativo</h2>
      <p><b>Concepto:</b> {b.concept}</p>
      <p><b>Tono:</b> {b.tone} · <b>Estilo:</b> {b.visual_style} · <b>Ritmo:</b> {b.pacing} · <b>Música:</b> {b.music_direction}</p>
      <table>
        <thead><tr><th>#</th><th>Sección</th><th>Duración</th><th>Dirección visual</th><th>Cámara</th><th>Transición</th></tr></thead>
        <tbody>
          {b.scenes.map((sc: any) => (
            <tr key={sc.index}><td>{sc.index}</td><td>{sc.section}</td><td>{sc.duration_s.toFixed(1)} s</td><td>{sc.visual_direction}</td><td>{sc.camera_motion}</td><td>{sc.transition}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VideoView({ id, arts, onChange }: { id: string; arts: Artifacts | null; onChange: () => void }) {
  const [scenes, setScenes] = useState("");
  const [from, setFrom] = useState("resource_generation");
  const act = useAction();
  const src = arts?.preview ?? arts?.master;
  const n = arts?.voice?.scenes?.length ?? 0;
  const redo = async () => {
    const list = scenes.split(",").map((x) => Number(x.trim())).filter((x) => Number.isInteger(x) && x >= 0 && x < n);
    if (!list.length) return;
    await act.run(() => api.post(`/api/projects/${id}/redo`, { scenes: list, from_phase: from, reason: "Petición desde la interfaz" }));
    onChange();
  };
  return (
    <div className="grid cols-2">
      <div className="panel">
        <h2>Visor de resultados</h2>
        {src ? <video controls src={fileUrl(id, src)} /> : <div className="empty">Aún no hay vídeo renderizado.</div>}
      </div>
      <div className="panel">
        <h2>Rehacer escenas concretas</h2>
        <p className="muted">Solo se regeneran las escenas indicadas; el resto se reutiliza.</p>
        <ErrorBox error={act.error} />
        <div className="row">
          <input placeholder={`Índices (0–${Math.max(0, n - 1)}), p. ej. 2,5`} value={scenes} onChange={(e) => setScenes(e.target.value)} />
          <select value={from} onChange={(e) => setFrom(e.target.value)}>
            <option value="resource_generation">Nueva imagen/clip</option>
            <option value="script">Reescribir narración</option>
            <option value="scene_prep">Nuevo prompt visual</option>
          </select>
          <button className="btn" disabled={act.busy || !n} onClick={redo}>Rehacer</button>
        </div>
        {arts?.assets && (
          <div className="thumbs" style={{ marginTop: 14 }}>
            {Object.entries(arts.assets as Record<string, any>).map(([k, a]) =>
              a.kind === "image" && String(a.path).includes(`/${id}/`) ? (
                <figure key={k} style={{ margin: 0 }}>
                  <img src={fileUrl(id, String(a.path).split(`/${id}/`)[1])} alt={`Escena ${k}`} loading="lazy" />
                  <figcaption className="muted mono">#{k} · {a.license?.name}</figcaption>
                </figure>
              ) : null,
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ReviewView({ arts }: { arts: Artifacts | null }) {
  const r = arts?.review;
  if (!r) return <div className="panel empty">Aún no hay revisión.</div>;
  return (
    <div className="grid cols-2">
      <div className="panel">
        <h2>Puntuación interna</h2>
        <div className="kpi">{r.score}<small>/ 100 · umbral {r.threshold}</small></div>
        <p>{r.passed ? <Badge status="approved" label="Apto" /> : <Badge status="in_review" label="Requiere correcciones" />}</p>
        <p className="muted">{r.disclaimer}</p>
        <h2>Editorial</h2>
        <p>{r.editorial.summary}</p>
        <table><tbody>{Object.entries(r.editorial.scores).map(([k, v]) => <tr key={k}><td>{k}</td><td>{String(v)}/10</td></tr>)}</tbody></table>
      </div>
      <div className="panel">
        <h2>Comprobaciones medidas</h2>
        <table>
          <tbody>
            {r.technical.map((c: any) => (
              <tr key={c.name}>
                <td>{c.passed ? "✅" : c.critical ? "⛔" : "⚠️"} {c.name}</td>
                <td className="muted">{c.detail}</td>
                <td className="mono">{c.points}/{c.max_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {r.corrections?.length > 0 && (
          <>
            <h2 style={{ marginTop: 12 }}>Correcciones solicitadas</h2>
            <ul>{r.corrections.map((c: any, i: number) => <li key={i}><b>{c.target_agent}</b>{c.scene_index != null ? ` (escena ${c.scene_index})` : ""}: {c.reason}</li>)}</ul>
          </>
        )}
      </div>
    </div>
  );
}

function ExportsView({ id, arts }: { id: string; arts: Artifacts | null }) {
  const ex = arts?.exports as Record<string, { path: string; duration_s: number; size_bytes: number; profile_verified_at: string | null }> | null;
  const results = arts?.publish_results as Record<string, { status: string; url?: string; message?: string }> | null;
  if (!ex) return <div className="panel empty">Las exportaciones se generan tras la aprobación final.</div>;
  return (
    <div className="grid cols-3">
      {Object.entries(ex).map(([platform, e]) => {
        const rel = e.path.split(`/${id}/`)[1];
        const thumb = arts?.publish_package?.[platform]?.thumbnail as string | undefined;
        return (
          <div key={platform} className="panel">
            <h2>{PLATFORM_LABEL[platform] ?? platform}</h2>
            <video controls src={fileUrl(id, rel)} poster={thumb ? fileUrl(id, thumb.split(`/${id}/`)[1]) : undefined} />
            <p className="mono">{e.duration_s.toFixed(1)} s · {(e.size_bytes / 1e6).toFixed(1)} MB</p>
            {!e.profile_verified_at && <p className="muted">Perfil de plataforma pendiente de verificar con la documentación oficial.</p>}
            <div className="row">
              <a className="btn" href={fileUrl(id, rel)} download>Descargar MP4</a>
              {results?.[platform] && <Badge status={results[platform].status === "skipped" ? "pending" : "completed"} label={results[platform].status} />}
            </div>
            {results?.[platform]?.url && <p><a href={results[platform].url} target="_blank" rel="noreferrer">{results[platform].url}</a></p>}
          </div>
        );
      })}
    </div>
  );
}

function Activity({ id, view }: { id: string; view: ProjectView }) {
  const { data } = useApi<YtEvent[]>(`/api/projects/${id}/events?limit=300`, { live: true });
  const costs = view.costs ?? [];
  return (
    <div className="grid cols-2">
      <div className="panel">
        <h2>Registro de actividad</h2>
        <div className="event-log">
          {[...(data ?? [])].reverse().map((e, i) => (
            <div key={i}>
              <span className="muted">{new Date(e.at).toLocaleTimeString("es-ES")}</span>
              <span>{e.agent ?? e.phase ?? "sistema"}</span>
              <span>{describeEvent(e.type, e.data)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>Memoria del proyecto</h2>
        <ul>{view.memory?.decisions.map((d, i) => <li key={i}><b>{d.by}:</b> {d.decision}</li>)}</ul>
        <h2>Consumo</h2>
        <p>Llamadas a Claude: <b>{view.llm_usage?.length ?? 0}</b> (indicativo)</p>
        <p>Coste externo: <b>{eur(costs.reduce((a, c) => a + Number((c as { amount_eur?: number }).amount_eur ?? 0), 0))}</b></p>
      </div>
    </div>
  );
}
