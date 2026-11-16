import { useState } from "react";
import { api } from "../api";
import { Badge, ErrorBox, PageHead, Progress, useAction, useApi } from "../components/ui";
import { CATEGORY_LABEL, PLATFORM_LABEL, shortDate, statusLabel } from "../format";
import type { ProjectSpec, ProjectSummary, ProjectView } from "../types";

const DEFAULT: ProjectSpec = {
  name: "",
  topic: "",
  idea: "",
  duration_s: 60,
  language: "es",
  intensity: "medium",
  platforms: ["youtube_shorts", "instagram_reels", "tiktok"],
  budget_max_eur: 0,
  mode: "auto",
  require_script_approval: true,
  subtitle_mode: null,
};

export function CreateForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [spec, setSpec] = useState<ProjectSpec>(DEFAULT);
  const [durationChoice, setDurationChoice] = useState("60");
  const [preferred, setPreferred] = useState<Record<string, string>>({});
  const { data: providers } = useApi<{ providers: { id: string; category: string; display_name: string; enabled: boolean }[] }>(
    "/api/providers",
  );
  const { busy, error, run } = useAction();
  const set = <K extends keyof ProjectSpec>(k: K, v: ProjectSpec[K]) => setSpec((s) => ({ ...s, [k]: v }));
  const custom = spec.mode === "custom";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: ProjectSpec = { ...spec, name: spec.name || spec.topic.slice(0, 60), preferred_providers: preferred };
    if (!custom) {
      Object.assign(body, { visual_style: null, narration_type: null, voice_type: null, music: null });
    }
    const res = await run(() => api.post<ProjectView>("/api/projects", body));
    if (res) onCreated(res.project.id);
  };

  const togglePlatform = (p: string) =>
    set("platforms", spec.platforms.includes(p) ? spec.platforms.filter((x) => x !== p) : [...spec.platforms, p]);

  return (
    <form className="panel" onSubmit={submit}>
      <div className="row" style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Nuevo vídeo</h2>
        <span className="spacer" />
        <div className="tabs" style={{ margin: 0 }}>
          <button type="button" className={`tab ${!custom ? "active" : ""}`} onClick={() => set("mode", "auto")}>
            Automático
          </button>
          <button type="button" className={`tab ${custom ? "active" : ""}`} onClick={() => set("mode", "custom")}>
            Personalizado
          </button>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="form-grid">
        <label className="field wide">
          Temática *
          <input required value={spec.topic} onChange={(e) => set("topic", e.target.value)} placeholder="p. ej. los secretos de los pulpos" />
        </label>
        <label className="field">
          Nombre del proyecto
          <input value={spec.name} onChange={(e) => set("name", e.target.value)} placeholder="(se usa la temática)" />
        </label>
        <label className="field">
          Duración
          <select
            value={durationChoice}
            onChange={(e) => {
              setDurationChoice(e.target.value);
              if (e.target.value !== "custom") set("duration_s", Number(e.target.value));
            }}
          >
            <option value="45">45 s</option>
            <option value="60">60 s</option>
            <option value="75">75 s</option>
            <option value="custom">Personalizada</option>
          </select>
        </label>
        {durationChoice === "custom" ? (
          <label className="field">
            Segundos (45–75)
            <input type="number" min={45} max={75} value={spec.duration_s} onChange={(e) => set("duration_s", Number(e.target.value))} />
          </label>
        ) : (
          <label className="field">
            Idioma
            <select value={spec.language} onChange={(e) => set("language", e.target.value)}>
              <option value="es">Español</option>
              <option value="en">Inglés</option>
              <option value="pt">Portugués</option>
              <option value="fr">Francés</option>
            </select>
          </label>
        )}
        <label className="field wide">
          Descripción de la idea {custom ? "" : "(opcional: el director decide el resto)"}
          <textarea value={spec.idea} onChange={(e) => set("idea", e.target.value)} />
        </label>
        {custom && (
          <>
            <label className="field">
              Estilo visual
              <input value={spec.visual_style ?? ""} onChange={(e) => set("visual_style", e.target.value || null)} placeholder="cinemático, documental…" />
            </label>
            <label className="field">
              Tipo de narración
              <input value={spec.narration_type ?? ""} onChange={(e) => set("narration_type", e.target.value || null)} placeholder="narrador en off…" />
            </label>
            <label className="field">
              Tipo de voz
              <input value={spec.voice_type ?? ""} onChange={(e) => set("voice_type", e.target.value || null)} placeholder="femenina, grave…" />
            </label>
            <label className="field">
              Música
              <input value={spec.music ?? ""} onChange={(e) => set("music", e.target.value || null)} placeholder="épica, calma… o 'none'" />
            </label>
          </>
        )}
        <label className="field">
          Intensidad del montaje
          <select value={spec.intensity} onChange={(e) => set("intensity", e.target.value as ProjectSpec["intensity"])}>
            <option value="low">Baja</option>
            <option value="medium">Media</option>
            <option value="high">Alta</option>
          </select>
        </label>
        <label className="field">
          Subtítulos
          <select value={spec.subtitle_mode ?? ""} onChange={(e) => set("subtitle_mode", (e.target.value || null) as ProjectSpec["subtitle_mode"])}>
            <option value="">Según plataforma</option>
            <option value="karaoke">Karaoke</option>
            <option value="word_pop">Palabra a palabra</option>
            <option value="line">Frase clásica</option>
          </select>
        </label>
        <label className="field">
          Presupuesto máximo (€)
          <input type="number" min={0} step={0.5} value={spec.budget_max_eur} onChange={(e) => set("budget_max_eur", Number(e.target.value))} />
        </label>
        <div className="field wide">
          Plataformas de destino
          <div className="row">
            {Object.entries(PLATFORM_LABEL).map(([k, v]) => (
              <label key={k} className="row" style={{ color: "var(--text)" }}>
                <input type="checkbox" checked={spec.platforms.includes(k)} onChange={() => togglePlatform(k)} /> {v}
              </label>
            ))}
          </div>
        </div>
        {custom && providers && (
          <div className="field wide">
            Proveedores preferidos (opcional)
            <div className="row">
              {["image", "tts", "music"].map((cat) => (
                <select key={cat} value={preferred[cat] ?? ""} onChange={(e) => setPreferred((p) => ({ ...p, [cat]: e.target.value }))}>
                  <option value="">{CATEGORY_LABEL[cat]}: el principal</option>
                  {providers.providers.filter((p) => p.category === cat && p.enabled).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              ))}
            </div>
          </div>
        )}
        <label className="row wide" style={{ color: "var(--text)" }}>
          <input type="checkbox" checked={spec.require_script_approval} onChange={(e) => set("require_script_approval", e.target.checked)} />
          Quiero aprobar el guion antes de producir
        </label>
      </div>
      <div className="row" style={{ marginTop: 14 }}>
        <span className="muted">Con presupuesto 0 € solo se usan proveedores locales y gratuitos.</span>
        <span className="spacer" />
        <button className="btn primary" disabled={busy || !spec.topic || spec.platforms.length === 0}>
          {busy ? "Creando…" : "Crear y producir"}
        </button>
      </div>
    </form>
  );
}

export default function Projects() {
  const { data, error } = useApi<ProjectSummary[]>("/api/projects", { live: true });
  const [showForm, setShowForm] = useState(false);
  return (
    <>
      <PageHead title="Proyectos" subtitle="Producciones, su avance real y lo que espera tu aprobación">
        <button className="btn primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cerrar" : "+ Nuevo vídeo"}
        </button>
      </PageHead>
      {showForm && <CreateForm onCreated={(id) => (location.hash = `#/projects/${id}`)} />}
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
