/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standard POC layout (STANDARD_POC.md): backend serves `frontend/dist/` at
// `/`. Tauri desktop shell and the "portable single HTML" build mode from the
// original app were dropped (web-only, cf. README "Ecarts au standard").
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? (process.env.VITE_BASE ?? "/") : "/",
  build: {
    target: "es2022",
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8007",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      include: ["src/core/**", "src/ports/**"],
    },
  },
}));
