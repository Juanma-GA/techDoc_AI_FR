import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

const e2ePort = process.env.ECM_AUTOMATION_E2E_PORT;
const apiProxyTarget = process.env.ECM_AUTOMATION_API_PROXY_TARGET ?? "http://127.0.0.1:8009";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Sous-chemin servi en prod (IIS) : sans ca, /assets/* renvoie 404 et l'UI est
  // blanche sous /app/<poc>/. L'IT build avec VITE_BASE=<sous-chemin>/.
  // Defaut '/' : preserve le serving local (dist a la racine) et le dev (serve).
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  server: {
    host: "127.0.0.1",
    port: Number(e2ePort ?? 5173),
    strictPort: e2ePort !== undefined,
    proxy: {
      "/api": apiProxyTarget,
    },
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    environment: "node",
  },
}));
