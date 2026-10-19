import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend } from "../../../../scripts/lib/frontend-build.mjs";
import { prepareDesktopIcons } from "../../../../scripts/lib/desktop-icons.mjs";
import { prepareBundledRuntime } from "./desktop-bundle.mjs";
import {
  createRuntimeSpec,
  prepareDevelopmentRuntime,
} from "./desktop-runtime.mjs";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const repo = path.resolve(frontend, "../../..");
const config = JSON.parse(readFileSync(path.join(frontend, "desktop.json"), "utf8"));
const mode = process.argv[2];

if (!["dev", "build"].includes(mode)) {
  throw new Error("Expected dev or build.");
}
if (process.platform !== "win32" || process.arch !== "x64") {
  throw new Error("The Image Processor desktop adapter currently supports Windows x64 only.");
}

prepareDesktopIcons(frontend, repo);
buildFrontend(repo, frontend, path.join(frontend, "dist"));
if (mode === "dev") {
  prepareDevelopmentRuntime(frontend);
} else {
  await prepareBundledRuntime(frontend, config);
}

const tauri = path.join(frontend, "src-tauri");
const runtime = path.join(tauri, "runtime");
const spec = createRuntimeSpec(frontend, config, mode);
for (const service of [spec.api, spec.lama]) {
  const commandRoot = mode === "dev" ? frontend : tauri;
  if (!existsSync(path.resolve(commandRoot, service.executable))) {
    throw new Error(`Missing desktop executable: ${service.executable}`);
  }
}

mkdirSync(runtime, { recursive: true });
writeFileSync(path.join(tauri, "runtime.json"), `${JSON.stringify(spec, null, 2)}\n`);
