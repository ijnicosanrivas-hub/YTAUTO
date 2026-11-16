import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { connectLive, parseHash, useLive } from "./store";
// Tipografía redondeada tipo LEGO, empaquetada con la app (funciona sin Internet)
import "@fontsource/lilita-one/400.css";
import "@fontsource/nunito/600.css";
import "@fontsource/nunito/700.css";
import "@fontsource/nunito/800.css";
import "./styles.css";

window.addEventListener("hashchange", () => useLive.getState().setRoute(parseHash(location.hash)));
connectLive();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
