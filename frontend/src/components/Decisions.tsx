import { useEffect, useMemo, useState } from "react";
import type { CreativeBriefView, ScenePromptView } from "../types";

const HOOK_STYLE: Record<string, string> = {
  pregunta: "Pregunta", dato_impactante: "Dato impactante", contradiccion: "Rompe un mito", in_medias_res: "En plena acción",
  promesa: "Promesa", visual_sorpresa: "Sorpresa visual", historia_personal: "Historia personal", reto: "Reto",
};

type Approve = (approved: boolean, note: string, data?: Record<string, unknown>) => void;

/** Concepto y gancho: el usuario elige entre 3 ganchos y ve la estrategia de retención antes de pagar el guion. */
export function ConceptDecision({ brief, busy, onDecide }: { brief: CreativeBriefView | null; busy: boolean; onDecide: Approve }) {
  const hooks = brief?.hook_options ?? [];
  const [pick, setPick] = useState(brief?.chosen_hook ?? 0);
  const [note, setNote] = useState("");
  useEffect(() => setPick(brief?.chosen_hook ?? 0), [brief?.chosen_hook]);
  if (!brief) return <p className="muted">Cargando el concepto…</p>;
  const total = brief.target_duration_s || 60;
  return (
    <div>
      <p>El director tiene el plan. <b>Elige el gancho</b> y dale el visto bueno (o pide otro enfoque) antes de escribir el guion: cambiarlo ahora cuesta una llamada, no un vídeo.</p>
      {hooks.length > 0 && (
        <div className="concept-grid" role="radiogroup" aria-label="Ganchos propuestos">
          {hooks.map((h, i) => (
            <button key={i} type="button" role="radio" aria-checked={pick === i} className={`hook-card ${pick === i ? "on" : ""}`} onClick={() => setPick(i)}>
              <span className="hook-style">{HOOK_STYLE[h.style] ?? h.style}{i === brief.chosen_hook ? " · favorito del director" : ""}</span>
              <span className="hook-text">«{h.text}»</span>
              {h.on_screen_text && <span className="hook-ost">{h.on_screen_text}</span>}
              {h.visual && <span className="small muted">🎬 {h.visual}</span>}
              {h.why && <span className="small">💡 {h.why}</span>}
            </button>
          ))}
        </div>
      )}
      <div className="concept-facts">
        {brief.viral_angle && <div><small>Por qué funcionará</small>{brief.viral_angle}</div>}
        {brief.target_viewer && <div><small>Para quién</small>{brief.target_viewer}</div>}
        {brief.story_structure && <div><small>Estructura</small>{brief.story_structure}</div>}
        {brief.opening_scene && <div><small>Primeros 3 segundos</small>{brief.opening_scene}</div>}
        <div><small>Estilo y tono</small>{brief.visual_style} · {brief.tone} · música {brief.music_direction}</div>
        {brief.cta && <div><small>Llamada a la acción</small>{brief.cta}</div>}
        {!!brief.title_options?.length && <div><small>Títulos</small>{brief.title_options.map((t) => <span key={t} className="fact-line">• {t}</span>)}</div>}
        {brief.cover_concept && <div><small>Portada</small>{brief.cover_concept}</div>}
        {!!brief.risks?.length && <div><small>Riesgos y cómo se evitan</small>{brief.risks.map((r) => <span key={r} className="fact-line">• {r}</span>)}</div>}
      </div>
      {!!brief.retention_plan?.length && (
        <>
          <h4>Plan de retención ({total} s)</h4>
          <div className="retention-line" aria-label="Plan de retención">
            {brief.retention_plan.map((b, i) => (
              <i key={i} style={{ left: `${Math.min(97, Math.max(3, (b.at_s / total) * 100))}%` }} title={`${b.at_s}s · ${b.technique}: ${b.detail ?? ""}`}>
                <span>{b.at_s}s {b.technique}</span>
              </i>
            ))}
          </div>
        </>
      )}
      <p className="muted small">{brief.scenes.length} escenas: {brief.scenes.map((s) => `${s.purpose}`).slice(0, 6).join(" · ")}{brief.scenes.length > 6 ? "…" : ""}</p>
      <div className="row">
        <input style={{ flex: 1 }} placeholder="Indicaciones para el guionista o qué cambiar (obligatorio para pedir otro enfoque)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn ok" disabled={busy} onClick={() => onDecide(true, note, { chosen_hook: pick })}>Aprobar con este gancho</button>
        <button className="btn danger" disabled={busy || !note.trim()} onClick={() => onDecide(false, note)}>Pedir otro enfoque</button>
      </div>
    </div>
  );
}

/** Storyboard: qué imagen o clip lleva cada escena, editable, antes de generarlos (gastan créditos). */
export function StoryboardDecision({ prompts, busy, onDecide }: { prompts: { style_guide?: string; prompts: ScenePromptView[] } | null; busy: boolean; onDecide: Approve }) {
  const list = useMemo(() => prompts?.prompts ?? [], [prompts]);
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [kinds, setKinds] = useState<Record<number, "image" | "video">>({});
  const [note, setNote] = useState("");
  if (!prompts) return <p className="muted">Cargando el storyboard…</p>;
  const clips = list.filter((p) => (kinds[p.scene_index] ?? p.kind) === "video").length;
  return (
    <div>
      <p>Storyboard listo: revisa qué se verá en cada escena. Puedes retocar el texto o pasar una escena de <b>clip</b> a <b>imagen</b> (los clips generados gastan más créditos). Nada se genera hasta que lo apruebes.</p>
      {prompts.style_guide && <p className="muted small">Guía visual: {prompts.style_guide}</p>}
      <div className="sb-grid">
        {list.map((p) => {
          const kind = kinds[p.scene_index] ?? p.kind;
          return (
            <div key={p.scene_index} className="sb-card">
              <div className="row">
                <b>Escena {p.scene_index + 1}</b>
                <span className="spacer" />
                <select value={kind} aria-label={`Tipo de recurso de la escena ${p.scene_index + 1}`} onChange={(e) => setKinds((k) => ({ ...k, [p.scene_index]: e.target.value as "image" | "video" }))}>
                  <option value="image">Imagen</option>
                  <option value="video">Clip de vídeo</option>
                </select>
              </div>
              <textarea value={edits[p.scene_index] ?? p.prompt} onChange={(e) => setEdits((x) => ({ ...x, [p.scene_index]: e.target.value }))} aria-label={`Descripción visual de la escena ${p.scene_index + 1}`} />
            </div>
          );
        })}
      </div>
      <p className="muted small">{list.length} escenas · {clips} con clip de vídeo · {list.length - clips} con imagen</p>
      <div className="row">
        <input style={{ flex: 1 }} placeholder="Comentario para rehacer el storyboard entero (obligatorio para rechazar)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn ok" disabled={busy} onClick={() => onDecide(true, note, { prompts: changedOnly(list, edits), kinds: changedKinds(list, kinds) })}>Aprobar y generar</button>
        <button className="btn danger" disabled={busy || !note.trim()} onClick={() => onDecide(false, note)}>Rehacer storyboard</button>
      </div>
    </div>
  );
}

export function changedOnly(list: ScenePromptView[], edits: Record<number, string>): Record<number, string> {
  return Object.fromEntries(Object.entries(edits).filter(([k, v]) => list.find((p) => p.scene_index === Number(k))?.prompt !== v && v.trim()));
}

export function changedKinds(list: ScenePromptView[], kinds: Record<number, "image" | "video">): Record<number, string> {
  return Object.fromEntries(Object.entries(kinds).filter(([k, v]) => list.find((p) => p.scene_index === Number(k))?.kind !== v));
}
