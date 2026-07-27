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
  // Base path des assets. En build, surchargeable via VITE_BASE pour un
  // deploiement IIS en sous-chemin (ex. "/doc-writer/"). En dev, toujours "/".
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8002",
    },
  },
}));
