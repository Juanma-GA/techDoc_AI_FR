import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import path from "node:path";

// `import x from "./f.docx?b64"` -> chaine base64 embarquee dans le bundle (inputs de demo
// factices, cf. src/demo/samples.ts). `?inline` ne s'applique pas aux formats Office.
function base64Import(): Plugin {
  return {
    name: "flowchart-generator:b64",
    enforce: "pre",
    load(id) {
      if (!id.endsWith("?b64")) return null;
      const file = id.slice(0, -"?b64".length);
      return `export default ${JSON.stringify(readFileSync(file).toString("base64"))};`;
    },
  };
}

export default defineConfig(({ command }) => ({
  plugins: [base64Import(), react()],
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
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8010",
    },
  },
}));
