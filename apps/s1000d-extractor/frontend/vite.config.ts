import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Sous-chemin servi en prod (IIS) : sans ca, /assets/* renvoie 404 et l'UI est
  // blanche sous /app/s1000d-extractor/. L'IT build avec VITE_BASE=<sous-chemin>/.
  // Defaut '/' : preserve le serving local (dist a la racine) et le dev (serve).
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": process.env.VITE_DEV_API_PROXY ?? "http://127.0.0.1:8004",
    },
  },
}));
