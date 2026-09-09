/// <reference types="vitest" />
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ command }) => ({
  // Sous-chemin IIS : `VITE_BASE=/doc-reviewer/` au build injecte le prefixe
  // dans les URLs d'assets. En dev on reste a la racine.
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": {
        target: "http://localhost:8003",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    css: false,
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
  },
}));
