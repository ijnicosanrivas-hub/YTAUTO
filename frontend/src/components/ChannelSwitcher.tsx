import { useEffect, useRef, useState } from "react";
import { useLive } from "../store";
import type { Channel, ChannelOverview } from "../types";
import { Face } from "./Face";

/** Arriba a la izquierda: la cara del director del canal activo. Al pulsar se despliegan los demás canales. */
export function ChannelSwitcher({ channels, overview }: { channels: Channel[]; overview: ChannelOverview[] }) {
  const channel = useLive((s) => s.channel);
  const setChannel = useLive((s) => s.setChannel);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const current = channels.find((c) => c.id === channel) ?? channels[0];
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);
  if (!current) return null;
  const busy = (id: string) => overview.find((o) => o.channel.id === id)?.running_agents.length ?? 0;
  const pick = (id: string) => {
    setChannel(id);
    setOpen(false);
    location.hash = "#/dashboard";
  };
  return (
    <div className="ch-switch" ref={box}>
      <button className="ch-current" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu"
        title="Cambiar de canal" style={{ ["--ch" as string]: current.accent }}>
        <Face theme={current.theme} agent="director" persona={current.director} size={64} image={current.has_director_image} ring={current.accent} />
        <span className="ch-text">
          <b>{current.name}</b>
          <small>{current.director?.character ?? "Director"} · dirige</small>
        </span>
        <span className="ch-caret" aria-hidden>{open ? "▴" : "▾"}</span>
        {busy(current.id) > 0 && <span className="ch-live" title="Agentes trabajando">{busy(current.id)}</span>}
      </button>
      {open && (
        <div className="ch-menu" role="menu" aria-label="Canales">
          {channels.map((c) => (
            <button key={c.id} role="menuitem" className={`ch-option${c.id === channel ? " active" : ""}`} onClick={() => pick(c.id)}
              style={{ ["--ch" as string]: c.accent }}>
              <Face theme={c.theme} agent="director" persona={c.director} size={56} image={c.has_director_image} ring={c.accent} />
              <span className="ch-text">
                <b>{c.name}</b>
                <small>{c.director?.character}</small>
              </span>
              {busy(c.id) > 0 ? <span className="ch-live">{busy(c.id)} trabajando</span> : <span className="ch-idle">en espera</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
