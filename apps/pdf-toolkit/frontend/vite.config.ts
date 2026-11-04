import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, frontendRoot, "VITE_");
  return {
    plugins: [
      react(),
      {
        name: "desktop-splash-theme",
        generateBundle() {
          this.emitFile({
            type: "asset",
            fileName: "theme.css",
            source: readFileSync(
              path.resolve(frontendRoot, "../../../framework/design-tokens/theme.css"),
              "utf8",
            ),
          });
        },
      },
    ],
    base: env.VITE_BASE ?? "/",
    resolve: {
      alias: {
        "@": path.resolve(frontendRoot, "src"),
      },
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": "http://127.0.0.1:8085",
      },
    },
    build: {
      outDir: path.resolve(frontendRoot, "../backend/web/static/generated"),
      emptyOutDir: true,
      assetsDir: "assets",
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
