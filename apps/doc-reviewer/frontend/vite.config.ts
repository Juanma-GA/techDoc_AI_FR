/// <reference types="vitest" />
import path from "node:path";
import { fileURLToPath } from "node:url";
import { request } from "node:http";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_BACKEND_PORT = 8003;
const BACKEND_PORT_LIMIT = DEFAULT_BACKEND_PORT + 20;

function configuredBackendPort(): number | null {
  const value = Number(process.env.VITE_BACKEND_PORT);
  return Number.isInteger(value) && value > 0 && value <= 65535 ? value : null;
}

function isDocReviewerBackend(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const probe = request(
      {
        hostname: "127.0.0.1",
        port,
        path: "/api/v1/health",
        method: "GET",
        timeout: 300,
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk: string) => {
          body += chunk;
        });
        response.on("end", () => {
          try {
            const payload = JSON.parse(body) as { status?: unknown; db?: unknown };
            resolve(
              response.statusCode === 200 &&
                typeof payload.status === "string" &&
                typeof payload.db === "string",
            );
          } catch {
            resolve(false);
          }
        });
      },
    );
    probe.on("error", () => resolve(false));
    probe.on("timeout", () => {
      probe.destroy();
      resolve(false);
    });
  });
}

async function resolveBackendTarget(): Promise<string> {
  const explicitPort = configuredBackendPort();
  if (explicitPort !== null) return `http://127.0.0.1:${explicitPort}`;

  for (let port = DEFAULT_BACKEND_PORT; port <= BACKEND_PORT_LIMIT; port += 1) {
    if (await isDocReviewerBackend(port)) return `http://127.0.0.1:${port}`;
  }

  return `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`;
}

export default defineConfig(async ({ command }) => ({
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
        target: command === "serve" ? await resolveBackendTarget() : `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`,
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
