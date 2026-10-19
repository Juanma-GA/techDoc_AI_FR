import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, run } from "../../../../scripts/lib/frontend-build.mjs";
import { prepareBundledRuntime } from "./desktop-bundle.mjs";
import {
  createRuntimeSpec,
  prepareDevelopmentRuntime,
} from "./desktop-runtime.mjs";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const repo = path.resolve(frontend, "../../..");
const config = JSON.parse(readFileSync(path.join(frontend, "desktop.json"), "utf8"));
const mode = process.argv[2];

function prepareAppIcon() {
  const icons = path.join(frontend, "src-tauri", "icons");
  const source = path.join(icons, "source.svg");
  const logo = path.join(repo, "packages", "ui", "src", "assets", "ai4techdoc.svg");
  const svg = readFileSync(logo, "utf8");
  const outputs = ["icon.ico", "icon.png"].map((name) => path.join(icons, name));
  if (
    existsSync(source)
    && readFileSync(source, "utf8") === svg
    && outputs.every(existsSync)
  ) {
    return;
  }

  mkdirSync(icons, { recursive: true });
  writeFileSync(source, svg);
  run("pnpm", ["exec", "tauri", "icon", "src-tauri/icons/source.svg", "--output", "src-tauri/icons"], frontend);
}

if (!["dev", "build"].includes(mode)) {
  throw new Error("Expected dev or build.");
}
if (process.platform !== "win32" || process.arch !== "x64") {
  throw new Error("The Image Processor desktop adapter currently supports Windows x64 only.");
}

prepareAppIcon();
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
