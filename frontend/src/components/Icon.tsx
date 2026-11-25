/** Iconos de línea (24×24, trazo redondeado), dibujados a mano para no depender de librerías externas. */
const P: Record<string, string> = {
  panel: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  plus: "M12 5v14M5 12h14",
  projects: "M4 7h16v13H4zM4 7l2-3h5l2 3M9 12l5 3-5 3z",
  room: "M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5",
  agents: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M17 11a2.5 2.5 0 1 0 0-5M17.5 14c2 .6 3.5 2.6 3.5 5",
  key: "M14 10a4 4 0 1 0-3.5 3.97L10 14v3h-2v2H5v-3l5.03-5.03A4 4 0 0 0 14 10zM15.5 8.5h.01",
  library: "M4 5h6v14H4zM10 5h4v14h-4zM15 6l4-1 2 13-4 1z",
  plug: "M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0zM12 16v5",
  wallet: "M4 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a1 1 0 0 1-1-1zM4 7l11-3v3M16 13.5h.01",
  sparkles: "M12 3l1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  history: "M3 12a9 9 0 1 0 3-6.7M3 4v4h4M12 7v5l3 2",
  chevron: "M6 9l6 6 6-6",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  coins: "M9 8c3.3 0 6-1.1 6-2.5S12.3 3 9 3 3 4.1 3 5.5 5.7 8 9 8zM3 5.5v4C3 10.9 5.7 12 9 12s6-1.1 6-2.5v-4M15 10.5c3.3 0 6 1.1 6 2.5s-2.7 2.5-6 2.5M9 12v4c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-3",
  check: "M5 12.5l4.5 4.5L19 7.5",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  play: "M8 5l11 7-11 7z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  alert: "M12 3l10 18H2zM12 10v4M12 17.5h.01",
  film: "M4 4h16v16H4zM8 4v16M16 4v16M4 8h4M4 12h4M4 16h4M16 8h4M16 12h4M16 16h4",
  chat: "M4 5h16v11H9l-5 4z",
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
  live: "M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM7.8 16.2a6 6 0 0 1 0-8.4M16.2 7.8a6 6 0 0 1 0 8.4M5 19a10 10 0 0 1 0-14M19 5a10 10 0 0 1 0 14",
  close: "M6 6l12 12M18 6L6 18",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
};

export function Icon({ name, size = 18, className, stroke = 1.8 }: { name: keyof typeof P | string; size?: number; className?: string; stroke?: number }) {
  return (
    <svg className={`icon ${className ?? ""}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={P[name] ?? P.panel} />
    </svg>
  );
}
