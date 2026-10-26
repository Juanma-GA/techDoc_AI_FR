import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  checkAppArtifacts,
  readAppRegistry,
  syncAppArtifacts,
} from "./lib/app-registry.mjs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const registry = readAppRegistry(repo);

if (process.argv.includes("--check")) {
  const mismatches = checkAppArtifacts(repo, registry);
  if (mismatches.length) {
    throw new Error(`App registry artifacts are out of date:\n${mismatches.join("\n")}`);
  }
  process.stdout.write("App registry artifacts are synchronized.\n");
} else {
  syncAppArtifacts(path.resolve(repo), registry);
  process.stdout.write("Synchronized package scripts and app inventory docs from scripts/apps.json.\n");
}
