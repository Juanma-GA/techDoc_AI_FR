/// <reference types="vitest" />
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ command }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Sous-chemin servi en prod (IIS) : sans ca, /assets/* renvoie 404 et l'UI
  // est blanche sous /Customizations/AtexisPOCS/corpus-agent/. L'IT build avec
  //   VITE_BASE=/Customizations/AtexisPOCS/corpus-agent/  (cf. DEPLOYMENT_GUIDE).
  // Defaut '/' : preserve le serving local (start.bat build dist + sert a la
  // racine) et le dev (`command === 'serve'`).
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  server: {
    // Bind explicite en IPv4 : `localhost` résout en `::1` (IPv6) sous Windows,
    // or start.bat ouvre http://127.0.0.1:5173 (IPv4) → sinon "connexion refusée".
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // Cible 127.0.0.1 (et non localhost/::1) : uvicorn bind 127.0.0.1.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    css: false,
  },
}));
