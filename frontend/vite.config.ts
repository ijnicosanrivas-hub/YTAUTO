import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, la API (FastAPI) corre en :8000 y Vite en :5173.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: { outDir: "dist", chunkSizeWarningLimit: 1500 },
  test: { environment: "jsdom" },
} as never);
