import { lazy, Suspense } from "react";
import { useApi } from "./components/ui";
import { useLive } from "./store";
import Agents from "./pages/Agents";
import Budget from "./pages/Budget";
import Dashboard from "./pages/Dashboard";
import Exports from "./pages/Exports";
import History from "./pages/History";
import Library from "./pages/Library";
import Models from "./pages/Models";
import ProjectDetail from "./pages/ProjectDetail";
import Projects from "./pages/Projects";
import Providers from "./pages/Providers";

// La sala 3D carga Three.js: se descarga solo al abrirla.
const ProductionRoom = lazy(() => import("./pages/ProductionRoom"));

const NAV: { page: string; label: string }[] = [
  { page: "dashboard", label: "Dashboard" },
  { page: "projects", label: "Proyectos" },
  { page: "room", label: "Sala de producción" },
  { page: "agents", label: "Agentes" },
  { page: "library", label: "Biblioteca" },
  { page: "providers", label: "Proveedores" },
  { page: "budget", label: "Presupuesto" },
  { page: "models", label: "Modelos Claude" },
  { page: "exports", label: "Exportaciones" },
  { page: "history", label: "Historial" },
];

export default function App() {
  const route = useLive((s) => s.route);
  const connected = useLive((s) => s.connected);
  const { data: dash } = useApi<{ waiting_approval: unknown[] }>("/api/dashboard", { live: true });
  const pending = dash?.waiting_approval.length ?? 0;

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

  return (
    <div className="layout">
      <nav className="sidebar" aria-label="Secciones">
        <div className="brand">
          <span className="brand-dot" /> YTAUTO
        </div>
        {NAV.map((n) => (
          <a key={n.page} href={`#/${n.page}`} className={`nav-item ${route.page === n.page ? "active" : ""}`}>
            {n.label}
            {n.page === "projects" && pending > 0 && <span className="nav-count">{pending}</span>}
          </a>
        ))}
        <div className="sidebar-foot">
          <span className={`badge ${connected ? "s-completed" : "s-error"}`}>
            {connected ? "En directo" : "Sin conexión"}
          </span>
        </div>
      </nav>
      <main className="main">{page}</main>
    </div>
  );
}
