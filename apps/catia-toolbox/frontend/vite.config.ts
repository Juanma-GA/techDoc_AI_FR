import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { existsSync } from "node:fs";
import path from "node:path";

export default defineConfig(({ command }) => {
  const input = [path.resolve(__dirname, "index.html")];
  const desktopStartup = path.resolve(__dirname, "src/desktop-startup.html");
  if (existsSync(desktopStartup)) input.push(desktopStartup);

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    // Sous-chemin servi en prod (IIS) : sans ca, /assets/* renvoie 404 et l'UI est
    // blanche sous /app/catia-toolbox/. L'IT build avec VITE_BASE=<sous-chemin>/.
    // Defaut '/' : preserve le serving local (dist a la racine) et le dev (serve).
    base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
    build: { rollupOptions: { input } },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": "http://127.0.0.1:8004",
      },
    },
  };
});
