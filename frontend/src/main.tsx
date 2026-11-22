import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { adoptTokenFromUrl } from "./api";
import { DEMO, startDemo } from "./demo/demo";
import { connectLive, parseHash, useLive } from "./store";
// Tipografías empaquetadas con la app (funcionan sin Internet). Base: Manrope. Rótulos de cada canal:
// Lilita One (Gotham/LEGO), Anton (Vice City), Fredoka (Kids) y Oswald (Deportes).
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/manrope/latin-800.css";
import "@fontsource/lilita-one/latin-400.css";
import "@fontsource/anton/latin-400.css";
import "@fontsource/fredoka/latin-500.css";
import "@fontsource/fredoka/latin-700.css";
import "@fontsource/oswald/latin-500.css";
import "@fontsource/oswald/latin-700.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "./styles.css";

adoptTokenFromUrl(); // si llegas desde el enlace del móvil, guarda el código de acceso
window.addEventListener("hashchange", () => useLive.getState().setRoute(parseHash(location.hash)));
if (DEMO) startDemo(); else connectLive();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
