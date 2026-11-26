import { useMemo, useState } from "react";
import { api } from "../api";
import { durationFromAnswer, groupByChannel, licenseWarning, nameFromIdea, tokens } from "../channels";
import { Face } from "../components/Face";
import { ErrorBox, PageHead, useAction, useApi } from "../components/ui";
import { PLATFORM_LABEL } from "../format";
import { estimateAudioCredits, fmtCredits, paidAccounts, videoAudioOptions } from "../accounts";
import { useLive } from "../store";
import { MUSIC_CHOICES, musicSpec, musicWarnings } from "../music";
import type { AccountsView, BriefQuestions, Channel, LicensesView, ProjectSpec, ProjectView, YtMusicView } from "../types";

const AGENTS = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];
const ROLE: Record<string, string> = {
  chief: "Jefe", director: "Director", scriptwriter: "Guionista", resources: "Recursos", voice: "Voz",
  editor: "Editor", sound: "Sonido", reviewer: "Revisor", publisher: "Publicador",
};
const STEPS = ["Tu idea", "El director pregunta", "Licencias por agente", "Lanzar"];

export default function NewProject() {
  const channel = useLive((s) => s.channel);
  const theme = useLive((s) => s.theme);
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const ch = channels?.find((c) => c.id === channel);
  const [step, setStep] = useState(0);
  const [idea, setIdea] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["youtube_shorts", "instagram_reels", "tiktok"]);
  const [language, setLanguage] = useState("es");
  const [brief, setBrief] = useState<BriefQuestions | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [picked, setPicked] = useState<Record<string, string>>({}); // agente → licencia ("" = automática)
  const [approveScript, setApproveScript] = useState(true);
  const [approveConcept, setApproveConcept] = useState(true); // elegir gancho y enfoque antes del guion
  const [approveStoryboard, setApproveStoryboard] = useState(true); // revisar imágenes/clips antes de gastar créditos
  const [musicChoice, setMusicChoice] = useState<string>("auto");
  const [musicStyle, setMusicStyle] = useState("");
  const { data: ytMusic } = useApi<YtMusicView>(musicChoice === "youtube" ? "/api/music/youtube" : null);
  const musicWarn = musicWarnings(musicChoice, ytMusic?.tracks.filter((x) => x.usable).length ?? null, platforms);
  const { data: lic } = useApi<LicensesView>(step >= 2 ? "/api/licenses" : null);
  const { data: plan } = useApi<{ plan: Record<string, string | null> }>(step >= 2 ? `/api/licenses/plan?channel=${channel}` : null);
  const { data: accounts } = useApi<AccountsView>(step >= 3 ? "/api/accounts" : null);
  const [spend, setSpend] = useState<Record<string, boolean>>({}); // cuenta de pago → autorizada en este vídeo
  const [budgetEur, setBudgetEur] = useState("5");
  const paid = paidAccounts(accounts);
  const audioOptions = videoAudioOptions(accounts);
  const [audioOff, setAudioOff] = useState<Set<string>>(new Set()); // lo que quitas solo para este vídeo
  const audioFeatures = audioOptions.map((f) => f.id).filter((id) => !audioOff.has(id));
  const always = accounts?.always ?? [];
  const spending = paid.some((a) => spend[a.id]) || always.length > 0;
  const ask = useAction();
  const launch = useAction();

  const byId = useMemo(() => Object.fromEntries((lic?.licenses ?? []).map((l) => [l.id, l])), [lic]);
  const chName = (id: string) => channels?.find((c) => c.id === id)?.name ?? id;
  const effective = (agent: string) => picked[agent] || plan?.plan[agent] || "";
  const duration = durationFromAnswer(answers.duration) ?? 60;

  const startBriefing = async () => {
    const res = await ask.run(() => api.post<BriefQuestions>("/api/briefing", { channel, idea }));
    if (res) {
      setBrief(res);
      setAnswers((a) => ({ duration: a.duration ?? "60 s", quality: a.quality ?? "Equilibrado", ...a }));
      setStep(1);
    }
  };

  const submit = async () => {
    const qa = (brief?.questions ?? []).map((q) => ({ question: q.question, answer: (answers[q.id] ?? "").trim() })).filter((x) => x.answer);
    const license_map = Object.fromEntries(Object.entries(picked).filter(([, v]) => v));
    const body: ProjectSpec = {
      name: nameFromIdea(idea), topic: nameFromIdea(idea), idea, duration_s: duration, language, intensity: "medium",
      ...musicSpec(musicChoice, musicStyle),
      platforms, budget_max_eur: spending ? Math.max(0, Number(budgetEur) || 0) : 0, mode: "auto", require_script_approval: approveScript,
      audio_features: audioFeatures,
      require_concept_approval: approveConcept, require_storyboard_approval: approveStoryboard, subtitle_mode: null,
      channel, brief: qa, license_map,
    };
    const res = await launch.run(async () => {
      const created = await api.post<ProjectView>("/api/projects", body);
      // Autorizaciones de gasto explícitas y registradas (puerta spend:<cuenta>), solo las marcadas.
      for (const a of paid.filter((x) => spend[x.id]))
        await api.post(`/api/projects/${created.project.id}/approve`, { gate: `spend:${a.id}`, approved: true, note: "Autorizado al crear el vídeo" });
      return created;
    });
    if (res) location.hash = `#/projects/${res.project.id}`;
  };

  return (
    <>
      <PageHead title="Nuevo vídeo" subtitle={`Cuéntale la idea a ${ch?.director?.character ?? "tu director"}, contesta sus preguntas, elige las licencias y lanza la producción en ${ch?.name ?? channel}.`} />
      <ol className="stepper" aria-label="Pasos">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? "active" : i < step ? "done" : ""}>
            <button type="button" disabled={i > step} onClick={() => setStep(i)}><span>{i + 1}</span>{s}</button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="panel wizard">
          <div className="director-say">
            <Face theme={ch?.theme ?? theme.id} agent="director" persona={ch?.director} size={72} image={ch?.has_director_image} />
            <div>
              <b>{ch?.director?.character ?? "Director"}</b>
              <p>Cuéntame la idea tal cual la tienes, aunque esté sin pulir. Antes de empezar te haré unas preguntas para entenderla bien.</p>
            </div>
          </div>
          <label className="field wide">Tu idea
            <textarea className="idea" value={idea} onChange={(e) => setIdea(e.target.value)} autoFocus
              placeholder="p. ej. algo sobre por qué los tiburones llevan existiendo más que los árboles, que enganche desde el primer segundo…" />
          </label>
          <div className="form-grid">
            <div className="field wide">Plataformas
              <div className="row">
                {Object.entries(PLATFORM_LABEL).map(([k, v]) => (
                  <label key={k} className="row" style={{ color: "var(--text)" }}>
                    <input type="checkbox" checked={platforms.includes(k)} onChange={() => setPlatforms((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]))} /> {v}
                  </label>
                ))}
              </div>
            </div>
            <label className="field">Idioma
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="es">Español</option><option value="en">Inglés</option><option value="pt">Portugués</option><option value="fr">Francés</option>
              </select>
            </label>
            <label className="field">Música
              <select value={musicChoice} onChange={(e) => setMusicChoice(e.target.value)}>
                {MUSIC_CHOICES.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </label>
            {musicChoice !== "none" && (
              <label className="field">Estilo de la música <small className="muted">(opcional)</small>
                <input value={musicStyle} onChange={(e) => setMusicStyle(e.target.value)} placeholder="p. ej. épica y tensa, alegre, tranquila…" />
              </label>
            )}
          </div>
          {musicWarn.map((w) => (
            <div key={w.text} className={`alert ${w.level === "info" ? "info" : ""}`}>
              <span>{w.text}{w.link && <> <a href={w.link}>Importar pistas</a></>}</span>
            </div>
          ))}
          <ErrorBox error={ask.error} />
          <div className="row">
            <span className="spacer" />
            <button className="btn primary" disabled={ask.busy || idea.trim().length < 3 || !platforms.length} onClick={startBriefing}>
              {ask.busy ? "El director está pensando…" : "Hablar con el director →"}
            </button>
          </div>
        </div>
      )}

      {step === 1 && brief && (
        <div className="panel wizard">
          <div className="director-say">
            <Face theme={ch?.theme ?? theme.id} agent="director" persona={ch?.director} size={72} image={ch?.has_director_image} />
            <div>
              <b>{brief.director?.character ?? "Director"}</b>
              <p>{brief.reading}</p>
              {brief.source === "base" && <p className="muted small">Claude no está disponible ahora: uso mi cuestionario base.</p>}
            </div>
          </div>
          <div className="chat">
            {brief.questions.map((q) => (
              <div key={q.id} className="question">
                <span className="q-avatar"><Face theme={ch?.theme ?? theme.id} agent="director" persona={ch?.director} size={40} image={ch?.has_director_image} /></span>
                <div className="bubble">
                  <label htmlFor={`q-${q.id}`}><b>{q.question}</b></label>
                  {q.why && <div className="muted small">{q.why}</div>}
                </div>
                <div className="answer">
                  {q.kind === "choice" && q.options.length > 0 && (
                    <div className="chips">
                      {q.options.map((o) => (
                        <button type="button" key={o} className={`chip${answers[q.id] === o ? " on" : ""}`} onClick={() => setAnswers((a) => ({ ...a, [q.id]: o }))}>{o}</button>
                      ))}
                    </div>
                  )}
                  <input id={`q-${q.id}`} value={answers[q.id] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    placeholder={q.kind === "choice" ? "…o escribe tu propia respuesta" : "Tu respuesta (puedes dejarla vacía)"} />
                </div>
              </div>
            ))}
          </div>
          <div className="row">
            <button className="btn" onClick={() => setStep(0)}>← Idea</button>
            <span className="muted">Duración: {duration} s</span>
            <span className="spacer" />
            <button className="btn primary" onClick={() => setStep(2)}>Elegir licencias →</button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="panel wizard">
          <h2>¿Qué licencia usa cada agente?</h2>
          <p className="muted">Por defecto cada agente usa las licencias de su canal. Si una se agota o este canal va muy bien, asígnale otra del pool.</p>
          <table className="lic-assign">
            <thead><tr><th>Agente</th><th>Licencia</th><th>Uso este mes</th><th /></tr></thead>
            <tbody>
              {AGENTS.map((a) => {
                const l = byId[effective(a)];
                const warn = licenseWarning(l, channel);
                return (
                  <tr key={a}>
                    <td>
                      <div className="row" style={{ gap: 10 }}>
                        <Face theme={ch?.theme ?? theme.id} agent={a} persona={theme.agents[a]} size={36} />
                        <div><b>{theme.agents[a]?.character ?? ROLE[a]}</b><div className="muted small">{ROLE[a]}</div></div>
                      </div>
                    </td>
                    <td>
                      <select value={picked[a] ?? ""} onChange={(e) => setPicked((p) => ({ ...p, [a]: e.target.value }))} aria-label={`Licencia de ${ROLE[a]}`}>
                        <option value="">Automática{plan?.plan[a] && byId[plan.plan[a]!] ? ` (${byId[plan.plan[a]!].name})` : " (sesión principal)"}</option>
                        {groupByChannel(lic?.licenses ?? [], (lic?.channels ?? []).map((c) => c.id)).filter(([, list]) => list.length).map(([cid, list]) => (
                          <optgroup key={cid} label={chName(cid)}>
                            {list.map((x) => (
                              <option key={x.id} value={x.id} disabled={!x.enabled}>
                                {x.name} · {x.plan}{x.limited_now ? " · agotada" : ""}{x.usage_pct != null ? ` · ${x.usage_pct}%` : ""}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </td>
                    <td className="mono">{l ? tokens(l.tokens.month) : "—"}</td>
                    <td>{warn && <span className={`badge ${l?.limited_now ? "s-error" : "s-in_review"}`}>{warn}</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!lic?.licenses.length && <div className="alert">Aún no hay licencias: todo irá por la sesión principal de Claude. <a href="#/licenses">Añadir licencias</a></div>}
          <div className="row">
            <button className="btn" onClick={() => setStep(1)}>← Preguntas</button>
            <span className="spacer" />
            <button className="btn primary" onClick={() => setStep(3)}>Revisar →</button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="panel wizard">
          <h2>Listo para producir</h2>
          <div className="grid cols-2">
            <div>
              <h4>Idea</h4>
              <p>{idea}</p>
              <h4>Respuestas al director</h4>
              <ul className="qa">
                {(brief?.questions ?? []).filter((q) => answers[q.id]?.trim()).map((q) => <li key={q.id}><span className="muted">{q.question}</span> {answers[q.id]}</li>)}
              </ul>
            </div>
            <div>
              <h4>Licencias</h4>
              <ul className="qa">
                {AGENTS.map((a) => <li key={a}><span className="muted">{ROLE[a]}:</span> {byId[effective(a)]?.name ?? "sesión principal"}{picked[a] ? "" : " (auto)"}</li>)}
              </ul>
              <h4 style={{ marginTop: 12 }}>Antes de gastar, quiero decidir yo</h4>
              <div className="gate-list">
                <label className="gate-item">
                  <input type="checkbox" checked={approveConcept} onChange={(e) => setApproveConcept(e.target.checked)} />
                  <span><b>Concepto y gancho</b><small className="muted">Eliges entre 3 ganchos, la estructura y el plan de retención antes de escribir el guion.</small></span>
                </label>
                <label className="gate-item">
                  <input type="checkbox" checked={approveScript} onChange={(e) => setApproveScript(e.target.checked)} />
                  <span><b>Guion</b><small className="muted">Lees el texto completo antes de grabar la voz.</small></span>
                </label>
                <label className="gate-item">
                  <input type="checkbox" checked={approveStoryboard} onChange={(e) => setApproveStoryboard(e.target.checked)} />
                  <span><b>Storyboard</b><small className="muted">Revisas qué imagen o clip lleva cada escena antes de generarlos (créditos).</small></span>
                </label>
              </div>
              {audioOptions.length > 0 && (
                <div className="spend-box">
                  <h4>Audio de este vídeo (ElevenLabs)</h4>
                  <div className="audio-video">
                    {audioOptions.map((f) => (
                      <label key={f.id} className="spend-item">
                        <input type="checkbox" checked={!audioOff.has(f.id)} onChange={() => setAudioOff((s) => { const n = new Set(s); if (n.has(f.id)) n.delete(f.id); else n.add(f.id); return n; })} />
                        <span><b>{f.title}</b> <span className="muted small">· {f.cost}</span></span>
                      </label>
                    ))}
                  </div>
                  <div className="muted small">Estimación: ≈ {fmtCredits(estimateAudioCredits(duration, audioFeatures, accounts?.elevenlabs.sfx?.max_per_video ?? null))} créditos de ElevenLabs como máximo. Cambia tus opciones en <a href="#/accounts">Cuentas conectadas</a>.</div>
                </div>
              )}
              {(paid.length > 0 || always.length > 0) && (
                <div className="spend-box">
                  <h4>Cuentas de pago para este vídeo</h4>
                  <div className="spend-list">
                    {paid.map((a) => (
                      <label key={a.id} className={`spend-item ${a.low ? "low" : ""}`}>
                        <input type="checkbox" checked={!!spend[a.id]} onChange={(e) => setSpend((s) => ({ ...s, [a.id]: e.target.checked }))} />
                        <span><b>{a.label}</b> <span className="muted small">· {a.detail}{a.low ? " · saldo bajo" : ""}</span></span>
                      </label>
                    ))}
                    {always.length > 0 && <div className="muted small">Con autorización permanente: {always.join(", ")} (<a href="#/accounts">cambiar</a>)</div>}
                  </div>
                  {spending && (
                    <label className="row" style={{ marginTop: 8 }}>
                      Tope de gasto de este vídeo
                      <input type="number" min="0" step="0.5" value={budgetEur} onChange={(e) => setBudgetEur(e.target.value)} style={{ width: 90 }} /> €
                    </label>
                  )}
                  <div className="muted small">Si una cuenta no se marca, su parte se hace con las herramientas gratuitas.</div>
                </div>
              )}
              <p className="muted small">{duration} s · {platforms.map((p) => PLATFORM_LABEL[p]).join(", ")} · música: {MUSIC_CHOICES.find((m) => m.id === musicChoice)?.label}{musicStyle ? ` (${musicStyle})` : ""} · {spending ? `gasto máximo ${Number(budgetEur) || 0} €` : "sin gasto externo (0 €)"}</p>
            </div>
          </div>
          <ErrorBox error={launch.error} />
          <div className="row">
            <button className="btn" onClick={() => setStep(2)}>← Licencias</button>
            <span className="spacer" />
            <button className="btn primary big" disabled={launch.busy} onClick={submit}>{launch.busy ? "Lanzando…" : "🎬 Lanzar producción"}</button>
          </div>
        </div>
      )}
    </>
  );
}
