import { useState } from "react";
import { api } from "../api";
import { Icon } from "../components/Icon";
import { ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import type { YtMusicView, YtTrack } from "../types";

interface Pending { file: File; title: string; genre: string; mood: string; cc: boolean; attribution: string }

const MOOD_ES: Record<string, string> = {
  Angry: "Agresiva", Bright: "Luminosa", Calm: "Tranquila", Dark: "Oscura / tensa", Dramatic: "Dramática / épica",
  Funky: "Enérgica", Happy: "Alegre", Inspirational: "Inspiradora", Romantic: "Romántica", Sad: "Triste",
};

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("No se pudo leer el archivo"));
    r.readAsDataURL(file);
  });
}

const fmtDur = (s: number | null) => (s == null ? "—" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`);

function TrackRow({ t, moods, genres, onChanged }: { t: YtTrack; moods: string[]; genres: string[]; onChanged: () => void }) {
  const { busy, error, run } = useAction();
  const patch = async (b: Record<string, unknown>) => { if (await run(() => api.patch(`/api/music/youtube/${encodeURIComponent(t.file)}`, b))) onChanged(); };
  return (
    <tr>
      <td><b>{t.title ?? t.file}</b><div className="muted small">{t.artist ?? "artista sin indicar"}</div><ErrorBox error={error} /></td>
      <td>
        <select value={t.genre ?? ""} disabled={busy} onChange={(e) => void patch({ genre: e.target.value || null })}>
          <option value="">—</option>{genres.map((g) => <option key={g}>{g}</option>)}
        </select>
      </td>
      <td>
        <select value={t.mood ?? ""} disabled={busy} onChange={(e) => void patch({ mood: e.target.value || null })}>
          <option value="">—</option>{moods.map((m) => <option key={m} value={m}>{MOOD_ES[m] ?? m}</option>)}
        </select>
      </td>
      <td className="mono">{fmtDur(t.duration_s)}</td>
      <td>
        {t.attribution_required
          ? <span className="badge s-in_review" title={t.attribution ?? ""}>Crédito obligatorio</span>
          : <span className="badge s-completed">Sin atribución</span>}
      </td>
      <td>
        <button className="btn danger" disabled={busy} onClick={async () => {
          if (!confirm(`¿Quitar «${t.title ?? t.file}» de YTAUTO?`)) return;
          if (await run(() => api.del(`/api/music/youtube/${encodeURIComponent(t.file)}`))) onChanged();
        }}>Quitar</button>
      </td>
    </tr>
  );
}

export default function YouTubeMusic() {
  const { data, error, reload } = useApi<YtMusicView>("/api/music/youtube");
  const [pending, setPending] = useState<Pending[]>([]);
  const [done, setDone] = useState(0);
  const { busy, error: importError, run } = useAction();
  const moods = data?.moods ?? [];
  const genres = data?.genres ?? [];

  const pick = (files: FileList | null) => {
    const list = Array.from(files ?? []).filter((f) => /\.(mp3|wav|m4a|ogg|flac)$/i.test(f.name));
    setPending((p) => [...p, ...list.map((file) => ({ file, title: file.name.replace(/\.[^.]+$/, ""), genre: "", mood: "", cc: false, attribution: "" }))]);
  };
  const set = (i: number, patch: Partial<Pending>) => setPending((p) => p.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  const missingCredit = pending.some((p) => p.cc && !p.attribution.trim());

  const importAll = async () => {
    setDone(0);
    const ok = await run(async () => {
      for (const p of pending) {
        await api.post("/api/music/youtube", {
          filename: p.file.name, data_b64: await toBase64(p.file), genre: p.genre || null, mood: p.mood || null,
          attribution_required: p.cc, attribution: p.cc ? p.attribution : null,
        });
        setDone((n) => n + 1);
      }
      return true;
    });
    if (ok) setPending([]);
    void reload();
  };

  return (
    <div>
      <PageHead title="Música de YouTube" subtitle="Pistas de la Biblioteca de audio de YouTube Studio para tus vídeos. Elige «Biblioteca de audio de YouTube Studio» en Nuevo vídeo para usarlas." />
      <div className="alert info">
        <Icon name="music" />
        <span>
          YouTube no ofrece una API para la Biblioteca de audio: las pistas se descargan a mano desde YouTube Studio y se importan aquí.
          Es música <b>libre de reclamaciones en YouTube</b> (Content ID no la reclama y se puede monetizar). Las de licencia
          Creative Commons exigen poner el crédito en la descripción: YTAUTO lo añade solo. YouTube no garantiza el uso fuera de
          YouTube, así que los paquetes de TikTok e Instagram llevan un aviso. <a href={data?.help_url ?? "https://support.google.com/youtube/answer/3376882"} target="_blank" rel="noreferrer">Ayuda oficial</a>
        </span>
      </div>
      <ErrorBox error={error} />
      <div className="grid cols-2">
        <div className="panel yt-steps">
          <h2>Cómo traer pistas</h2>
          <ol>
            <li>Abre la <a href={data?.audio_library_url ?? "https://www.youtube.com/audiolibrary"} target="_blank" rel="noreferrer">Biblioteca de audio de YouTube Studio</a> con la cuenta de tu canal.</li>
            <li>Filtra por género y estado de ánimo (y «Attribution not required» si no quieres créditos) y pulsa <b>Download</b>.</li>
            <li>Si la pista es Creative Commons, copia su texto de atribución (columna «License type» → icono CC → Copy).</li>
            <li>Arrastra aquí los MP3, indica género, ánimo y, si toca, pega el crédito.</li>
          </ol>
        </div>
        <label className={`panel yt-drop ${pending.length ? "has" : ""}`}
          onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files); }}>
          <Icon name="upload" size={30} />
          <b>Arrastra aquí los MP3 descargados</b>
          <span className="muted small">o pulsa para elegirlos · hasta 30 MB por pista</span>
          <input type="file" accept="audio/*,.mp3" multiple hidden onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
        </label>
      </div>

      {pending.length > 0 && (
        <div className="panel">
          <h2>Por importar ({pending.length})</h2>
          <div className="yt-pending">
            {pending.map((p, i) => (
              <div key={`${p.file.name}-${i}`} className="yt-item">
                <div className="row"><b>{p.title}</b><span className="muted small">{(p.file.size / 1e6).toFixed(1)} MB</span><span className="spacer" />
                  <button className="btn" onClick={() => setPending((x) => x.filter((_, k) => k !== i))}>Quitar</button></div>
                <div className="acc-two">
                  <label>Género<select value={p.genre} onChange={(e) => set(i, { genre: e.target.value })}><option value="">—</option>{genres.map((g) => <option key={g}>{g}</option>)}</select></label>
                  <label>Estado de ánimo<select value={p.mood} onChange={(e) => set(i, { mood: e.target.value })}><option value="">—</option>{moods.map((m) => <option key={m} value={m}>{MOOD_ES[m] ?? m}</option>)}</select></label>
                </div>
                <label className="row small"><input type="checkbox" checked={p.cc} onChange={(e) => set(i, { cc: e.target.checked })} /> Creative Commons: exige crédito en la descripción</label>
                {p.cc && <textarea rows={2} value={p.attribution} onChange={(e) => set(i, { attribution: e.target.value })} placeholder="Pega aquí el texto de atribución de YouTube Studio" />}
              </div>
            ))}
          </div>
          <ErrorBox error={importError} />
          <div className="row">
            {missingCredit && <span className="muted small">Falta pegar el crédito de alguna pista Creative Commons.</span>}
            <span className="spacer" />
            <button className="btn primary" disabled={busy || missingCredit} onClick={importAll}>
              {busy ? `Importando ${done + 1}/${pending.length}…` : `Importar ${pending.length} pista${pending.length > 1 ? "s" : ""}`}
            </button>
          </div>
        </div>
      )}

      <div className="panel">
        <h2>Tus pistas ({data?.tracks.length ?? 0})</h2>
        {data && data.tracks.length === 0 && <div className="empty">Aún no hay pistas. Descárgalas de YouTube Studio e impórtalas arriba.</div>}
        {data && data.tracks.length > 0 && (
          <div className="table-wrap">
            <table className="yt-table">
              <thead><tr><th>Pista</th><th>Género</th><th>Ánimo</th><th>Duración</th><th>Licencia</th><th /></tr></thead>
              <tbody>{data.tracks.map((t) => <TrackRow key={t.file} t={t} moods={moods} genres={genres} onChanged={reload} />)}</tbody>
            </table>
          </div>
        )}
        <p className="muted small">Al producir, el agente de sonido elige la pista cuyo ánimo encaja con el guion (p. ej. «tensa» → Dark/Dramatic, «alegre» → Happy/Bright). La voz la pone ElevenLabs; ElevenLabs no se usa para la música.</p>
      </div>
    </div>
  );
}
