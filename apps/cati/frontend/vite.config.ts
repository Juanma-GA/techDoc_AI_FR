import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ command }) => ({
  // Base publique : "/" en dev, VITE_BASE (sous-chemin IIS) au build si defini.
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8007",
    },
  },
}));
