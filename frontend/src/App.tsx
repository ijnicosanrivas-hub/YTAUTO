import { DEMO } from "./demo/demo";
import { lazy, Suspense, useEffect, useState } from "react";
import { UNAUTHORIZED_EVENT, setToken } from "./api";
import { useApi } from "./components/ui";
import { ChannelSwitcher } from "./components/ChannelSwitcher";
import { Icon } from "./components/Icon";
import { withChannel } from "./channels";
import { useLive } from "./store";
import type { Channel, ChannelOverview, Theme } from "./types";
import Agents from "./pages/Agents";
import Budget from "./pages/Budget";
import Dashboard from "./pages/Dashboard";
import Exports from "./pages/Exports";
import History from "./pages/History";
import Licenses from "./pages/Licenses";
import Monitor from "./pages/Monitor";
import NewProject from "./pages/NewProject";
import Library from "./pages/Library";
import Models from "./pages/Models";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Providers from "./pages/Providers";

// La sala 3D carga Three.js: se descarga solo al abrirla.
const ProductionRoom = lazy(() => import("./pages/ProductionRoom"));

const NAV: { title: string; items: { page: string; label: string; icon: string }[] }[] = [
  { title: "Producción", items: [
    { page: "dashboard", label: "Panel", icon: "panel" },
    { page: "new", label: "Nuevo vídeo", icon: "plus" },
    { page: "projects", label: "Proyectos", icon: "projects" },
    { page: "room", label: "Sala de agentes", icon: "room" },
  ] },
  { title: "Equipo", items: [
    { page: "agents", label: "Agentes", icon: "agents" },
    { page: "monitor", label: "Monitor de tokens", icon: "live" },
    { page: "licenses", label: "Licencias", icon: "key" },
    { page: "models", label: "Modelos Claude", icon: "sparkles" },
  ] },
  { title: "Recursos", items: [
    { page: "library", label: "Biblioteca", icon: "library" },
    { page: "providers", label: "Proveedores", icon: "plug" },
    { page: "budget", label: "Presupuesto", icon: "wallet" },
    { page: "exports", label: "Exportaciones", icon: "download" },
    { page: "history", label: "Historial", icon: "history" },
  ] },
];
const PAGE_LABEL: Record<string, string> = Object.fromEntries(NAV.flatMap((g) => g.items.map((i) => [i.page, i.label])));

/** Pide el código de acceso cuando el servidor lo exige (acceso desde el móvil) y falta o es incorrecto. */
function TokenGate() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  useEffect(() => {
    const on = () => setOpen(true);
    window.addEventListener(UNAUTHORIZED_EVENT, on);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, on);
  }, []);
  if (!open) return null;
  return (
    <div className="gate" role="dialog" aria-modal="true" aria-label="Código de acceso">
      <form
        className="panel gate-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (!value.trim()) return;
          setToken(value.trim());
          location.reload();
        }}
      >
        <h2>Código de acceso</h2>
        <p className="muted">Este programa pide un código. Está en la ventana negra del PC (o en el enlace de acceso desde el móvil).</p>
        <input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder="Código de acceso" autoCapitalize="off" autoCorrect="off" spellCheck={false} />
        <button className="btn primary" type="submit" style={{ marginTop: 10 }}>Entrar</button>
      </form>
    </div>
  );
}

export default function App() {
  const route = useLive((s) => s.route);
  const connected = useLive((s) => s.connected);
  const channel = useLive((s) => s.channel);
  const setChannel = useLive((s) => s.setChannel);
  const { data: dash } = useApi<{ waiting_approval: unknown[] }>(withChannel("/api/dashboard", channel), { live: true });
  const pending = dash?.waiting_approval.length ?? 0;
  const { data: channels } = useApi<Channel[]>("/api/channels");
  const { data: overview } = useApi<{ channels: ChannelOverview[] }>("/api/overview", { live: true });
  const theme = useLive((s) => s.theme);
  const setTheme = useLive((s) => s.setTheme);
  const { data: themeData } = useApi<Theme>(withChannel("/api/theme", channel));
  useEffect(() => {
    if (themeData) setTheme(themeData);
  }, [themeData, setTheme]);
  useEffect(() => {
    // canal guardado que ya no existe → el primero
    if (channels?.length && !channels.some((c) => c.id === channel)) setChannel(channels[0].id);
  }, [channels, channel, setChannel]);
  const current = channels?.find((c) => c.id === channel);
  useEffect(() => {
    // Estética general neutra para todas las pantallas; el perfil del canal solo aporta su color de acento.
    // Cada canal viste toda la app con su piel (colores, tipografía de rótulos, formas); ver styles.css.
    const root = document.documentElement;
    root.dataset.profile = current?.theme ?? theme.id;
    document.title = `${current?.name ?? "YTAUTO"} · YTAUTO`;
  }, [theme, current]);

  let page: React.ReactNode;
  switch (route.page) {
    case "projects":
      page = route.id ? <ProjectDetail id={route.id} /> : <Projects />;
      break;
    case "room":
      page = (
        <Suspense fallback={<div className="empty">Cargando sala 3D…</div>}>
          <ProductionRoom />
        </Suspense>
      );
      break;
    case "agents":
      page = <Agents />;
      break;
    case "new":
      page = <NewProject />;
      break;
    case "licenses":
      page = <Licenses />;
      break;
    case "monitor":
      page = <Monitor />;
      break;
    case "library":
      page = <Library />;
      break;
    case "providers":
      page = <Providers />;
      break;
    case "budget":
      page = <Budget />;
      break;
    case "models":
      page = <Models />;
      break;
    case "exports":
      page = <Exports />;
      break;
    case "history":
      page = <History />;
      break;
    default:
      page = <Dashboard />;
  }

  const pageLabel = route.page === "room" ? theme.room_title : PAGE_LABEL[route.page] ?? "Panel";
  return (
    <div className="layout">
      <nav className="sidebar" aria-label="Secciones">
        {channels?.length ? <ChannelSwitcher channels={channels} overview={overview?.channels ?? []} /> : <div className="brand">YTAUTO</div>}
        {NAV.map((g) => (
          <div key={g.title} className="nav-group">
            <div className="nav-group-title">{g.title}</div>
            {g.items.map((n) => (
              <a key={n.page} href={`#/${n.page}`} className={`nav-item ${route.page === n.page ? "active" : ""}`}>
                <Icon name={n.icon} />
                <span className="nav-label">{n.page === "room" ? theme.room_title : n.label}</span>
                {n.page === "projects" && pending > 0 && <span className="nav-count">{pending}</span>}
              </a>
            ))}
          </div>
        ))}
        <div className="sidebar-foot">
          <span className="brandmark"><i />YTAUTO · 4 CANALES</span>
        </div>
      </nav>
      <main className="main">
        <header className="topbar">
          <div className="crumbs"><span className="dot" />{current?.name ?? "YTAUTO"}<span>/</span><b>{pageLabel}</b></div>
          <span className="spacer" />
          <span className={`live-pill${connected || DEMO ? "" : " off"}`}><i />{DEMO ? "Demostración" : connected ? "En directo" : "Sin conexión"}</span>
          {route.page !== "new" && <a className="btn primary small" href="#/new"><Icon name="plus" size={15} />Nuevo vídeo</a>}
        </header>
        {page}
      </main>
      <TokenGate />
    </div>
  );
}
