import { existsSync, mkdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, run, sourceFiles } from "./lib/frontend-build.mjs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const app = path.join(repo, "apps", "pdf-toolkit");
const backend = path.join(app, "backend");
buildFrontend(repo, path.join(app, "frontend"), path.join(backend, "web", "static", "generated"), {
  allowStale: process.argv.includes("--allow-stale"),
});
const output = path.join(backend, "bin");
const binary = path.join(output,
  process.platform === "win32" ? "pdf-toolkit-backend.exe" : "pdf-toolkit-backend");
const inputs = ["cmd", "handlers", "pdf", "services", "web", "go.mod", "go.sum"]
  .flatMap((name) => sourceFiles(path.join(backend, name)));
const rebuild = !existsSync(binary) || inputs.some((file) => statSync(file).mtimeMs > statSync(binary).mtimeMs);
mkdirSync(output, { recursive: true });
if (rebuild) run("go", ["build", "-o", binary, "./cmd/pdf-toolkit"], backend);
else process.stdout.write("[backend] Go binary up to date.\n");
