import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ErrorBox, useAction } from "./ui";
import type { ElevenView } from "../types";

function PlanBadge({ ok, tier }: { ok: boolean | null; tier: string }) {
  if (ok === true) return <span className="badge s-completed">Incluido en tu plan</span>;
  if (ok === false) return <span className="badge s-error">Requiere plan {tier}</span>;
  return <span className="badge s-paused">Desde plan {tier}</span>;
}

/** Cuestionario: qué capacidades de ElevenLabs quieres usar (se aplican a los vídeos y se pueden quitar en cada uno). */
export function AudioQuestionnaire({ v, onChanged }: { v: ElevenView; onChanged: () => void }) {
  const features = useMemo(() => v.features ?? [], [v.features]);
  const [on, setOn] = useState<Set<string>>(new Set(features.filter((f) => f.enabled).map((f) => f.id)));
  const { busy, error, run } = useAction();
  useEffect(() => setOn(new Set(features.filter((f) => f.enabled).map((f) => f.id))), [features]);
  const toggle = (id: string) => setOn((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const dirty = features.some((f) => f.enabled !== on.has(f.id));
  return (
    <div className="panel audio-q">
      <div className="row">
        <h2 style={{ margin: 0 }}>¿Qué quieres usar de ElevenLabs?</h2>
        <span className="spacer" />
        {!v.features_answered && <span className="badge s-in_review">Contesta para empezar</span>}
      </div>
      <p className="muted small">Lo que marques se ofrecerá en cada «Nuevo vídeo» (ahí puedes quitarlo para ese vídeo). Nada gasta créditos sin tu autorización y el freno de saldo sigue activo.</p>
      <ErrorBox error={error} />
      <div className="aq-list">
        {features.map((f) => (
          <label key={f.id} className={`aq-item ${on.has(f.id) ? "on" : ""} ${f.in_app ? "" : "info"}`}>
            {f.in_app ? <input type="checkbox" checked={on.has(f.id)} onChange={() => toggle(f.id)} /> : <span className="aq-dot">i</span>}
            <span className="aq-body">
              <b>{f.title}</b>
              <span>{f.question}</span>
              <small className="muted">{f.what}</small>
              <span className="row" style={{ gap: 6 }}>
                <small className="mono">💳 {f.cost}</small>
                {f.in_app ? <PlanBadge ok={f.plan_ok} tier={f.min_tier} /> : <span className="badge s-paused">En la web de ElevenLabs</span>}
              </span>
            </span>
          </label>
        ))}
      </div>
      <div className="row">
        <span className="spacer" />
        <button className="btn primary" disabled={busy || (!dirty && !!v.features_answered)} onClick={async () => {
          if (await run(() => api.put("/api/accounts/elevenlabs/features", { features: [...on] }))) onChanged();
        }}>{v.features_answered ? "Guardar cambios" : "Guardar mis respuestas"}</button>
      </div>
    </div>
  );
}

interface Preview { generated_voice_id: string; audio_base_64: string; media_type: string }

/** Reparto de voces por canal + diseño de voces nuevas a partir de una descripción (Voice Design). */
export function VoiceCast({ v, onChanged }: { v: ElevenView; onChanged: () => void }) {
  const channels = v.channels ?? [];
  const roles = v.roles ?? {};
  const [channel, setChannel] = useState(channels[0]?.id ?? "general");
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([]);
  const [desc, setDesc] = useState("");
  const [previews, setPreviews] = useState<Preview[]>([]);
  const [pick, setPick] = useState<string>("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("narrador");
  const { busy, error, run } = useAction();
  const designOn = (v.features ?? []).some((f) => f.id === "voice_design" && f.enabled);
  const cast = v.cast?.[channel] ?? {};
  useEffect(() => {
    if (!v.has_key) return;
    api.get<{ id: string; name: string }[]>("/api/accounts/elevenlabs/voices").then(setVoices).catch(() => setVoices([]));
  }, [v.has_key, v.cast]);
  if (!v.linked) return null;
  const assign = async (r: string, voice_id: string) => {
    if (await run(() => api.put("/api/accounts/elevenlabs/cast", { channel, role: r, voice_id: voice_id || null }))) onChanged();
  };
  return (
    <div className="panel">
      <div className="row">
        <h2 style={{ margin: 0 }}>Voces de cada canal</h2>
        <span className="spacer" />
        <div className="seg">
          {channels.map((c) => <button key={c.id} className={`seg-btn ${channel === c.id ? "on" : ""}`} onClick={() => setChannel(c.id)}>{c.name}</button>)}
        </div>
      </div>
      <p className="muted small">La identidad sonora del canal: el narrador suena siempre igual y los personajes de los diálogos usan estas voces.</p>
      <ErrorBox error={error} />
      <div className="cast-grid">
        {Object.entries(roles).map(([r, label]) => (
          <label key={r} className="cast-row">
            <span>{label}</span>
            <select value={cast[r] ?? ""} disabled={busy} onChange={(e) => void assign(r, e.target.value)}>
              <option value="">— sin asignar —</option>
              {cast[r] && !voices.some((x) => x.id === cast[r]) && <option value={cast[r]}>{cast[r]}</option>}
              {voices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </label>
        ))}
      </div>
      {designOn && (
        <div className="design-box">
          <h4>Diseñar una voz nueva</h4>
          <textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Ej.: narrador masculino de voz grave y rasgada, misterioso, ritmo pausado, estilo documental de crímenes" />
          <div className="row">
            <button className="btn" disabled={busy || desc.trim().length < 10} onClick={async () => {
              const r = await run(() => api.post<{ previews: Preview[] }>("/api/accounts/elevenlabs/voice-design", { description: desc }));
              if (r) { setPreviews(r.previews); setPick(r.previews[0]?.generated_voice_id ?? ""); }
            }}>{busy ? "Generando…" : "Generar 3 muestras"}</button>
            <span className="muted small">ElevenLabs indica el coste al generar las muestras.</span>
          </div>
          {previews.length > 0 && (
            <>
              <div className="preview-list">
                {previews.map((p, i) => (
                  <label key={p.generated_voice_id} className={`preview ${pick === p.generated_voice_id ? "on" : ""}`}>
                    <input type="radio" checked={pick === p.generated_voice_id} onChange={() => setPick(p.generated_voice_id)} />
                    <span>Muestra {i + 1}</span>
                    <audio controls src={`data:${p.media_type};base64,${p.audio_base_64}`} />
                  </label>
                ))}
              </div>
              <div className="row">
                <input placeholder="Nombre de la voz" value={name} onChange={(e) => setName(e.target.value)} />
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {Object.entries(roles).map(([r, l]) => <option key={r} value={r}>{l}</option>)}
                </select>
                <button className="btn primary" disabled={busy || !pick || name.trim().length < 2} onClick={async () => {
                  if (await run(() => api.post("/api/accounts/elevenlabs/voice-design/save", { generated_voice_id: pick, name, description: desc, channel, role }))) {
                    setPreviews([]); setDesc(""); setName(""); onChanged();
                  }
                }}>Guardar para {channels.find((c) => c.id === channel)?.name}</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
