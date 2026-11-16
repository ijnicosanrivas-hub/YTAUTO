import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { connectLive, parseHash, useLive } from "./store";
import "./styles.css";

window.addEventListener("hashchange", () => useLive.getState().setRoute(parseHash(location.hash)));
connectLive();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
