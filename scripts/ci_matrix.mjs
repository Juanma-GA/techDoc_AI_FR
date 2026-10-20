import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { appCiMatrix, readAppRegistry } from "./lib/app-registry.mjs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const registry = readAppRegistry(repo);

for (const app of registry.apps) {
  const frontendDir = path.join(repo, "apps", app.slug, "frontend");
  const frontendManifest = path.join(frontendDir, "package.json");
  if (!existsSync(frontendManifest)) {
    throw new Error(`Frontend manifest is missing for ${app.slug}.`);
  }
  const frontend = JSON.parse(readFileSync(frontendManifest, "utf8"));
  for (const script of ["build", "test", "typecheck"]) {
    if (!frontend.scripts?.[script]) {
      throw new Error(`Frontend ${app.slug} is missing the ${script} script required by CI.`);
    }
  }
  if (app.e2e && !frontend.scripts?.["test:e2e"]) {
    throw new Error(`Frontend ${app.slug} is marked e2e but has no test:e2e script.`);
  }

  const backendManifest = app.backend === "go" ? "go.mod" : "pyproject.toml";
  if (!existsSync(path.join(repo, "apps", app.slug, "backend", backendManifest))) {
    throw new Error(`Backend manifest ${backendManifest} is missing for ${app.slug}.`);
  }
}

process.stdout.write(`${JSON.stringify(appCiMatrix(registry))}\n`);
