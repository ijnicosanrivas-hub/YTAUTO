import { useEffect, useRef, useState } from "react";
import { useLive } from "../store";
import type { Channel, ChannelOverview } from "../types";
import { ChannelArt } from "./ChannelArt";
import { Face } from "./Face";
import { Icon } from "./Icon";

/** Arriba a la izquierda: la cara del jefe del canal activo (el del centro de su sala). Al pulsar se despliegan los demás canales. */
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
        <Face theme={current.theme} agent="chief" persona={current.chief} size={64} image={current.has_chief_image} ring={current.accent} />
        <span className="ch-text">
          <b>{current.name}</b>
          <small>{current.chief?.character ?? "Jefe"} · al mando</small>
        </span>
        <span className="ch-caret" aria-hidden><Icon name="chevron" size={16} /></span>
        {busy(current.id) > 0 && <span className="ch-live" title="Agentes trabajando">{busy(current.id)}</span>}
      </button>
      {open && (
        <div className="ch-menu" role="menu" aria-label="Canales">
          <div className="ch-menu-title">Cambiar de canal</div>
          {channels.map((c) => (
            <button key={c.id} role="menuitem" className={`ch-option${c.id === channel ? " active" : ""}`} onClick={() => pick(c.id)}
              style={{ ["--ch" as string]: c.accent }}>
              <ChannelArt profile={c.theme} />
              <Face theme={c.theme} agent="chief" persona={c.chief} size={56} image={c.has_chief_image} ring={c.accent} />
              <span className="ch-text">
                <b>{c.name}</b>
                <small>{c.chief?.character}</small>
              </span>
              {busy(c.id) > 0 ? <span className="ch-live">{busy(c.id)} trabajando</span> : <span className="ch-idle">en espera</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
