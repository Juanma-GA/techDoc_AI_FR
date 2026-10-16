import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, run } from "../../../../scripts/lib/frontend-build.mjs";
import { prepareFastApi } from "../../../../scripts/lib/desktop-fastapi.mjs";
import { prepareDesktopIcons } from "../../../../scripts/lib/desktop-icons.mjs";

const frontend = fileURLToPath(new URL("../", import.meta.url));
const repo = path.resolve(frontend, "../../..");
const config = JSON.parse(readFileSync(path.join(frontend, "desktop.json"), "utf8"));
const mode = process.argv[2];
if (!["dev", "build"].includes(mode)) throw new Error("Expected dev or build.");
prepareDesktopIcons(frontend, repo);
buildFrontend(repo, frontend, path.join(frontend, "dist"));
if (config.adapter === "fastapi") {
  await prepareFastApi(frontend, mode);
} else if (config.adapter === "command") {
  const commands = config.prepare?.[mode];
  if (!Array.isArray(commands) || commands.length === 0) throw new Error("Missing backend preparation commands.");
  for (const [command, ...args] of commands) run(command, args, frontend);
} else {
  throw new Error(`Unsupported desktop adapter: ${config.adapter}`);
}
const spec = config[mode];
const root = mode === "dev" ? frontend : path.join(frontend, "src-tauri");
if (!existsSync(path.resolve(root, spec.executable))) {
  throw new Error(`Missing desktop executable: ${spec.executable}`);
}
const tauri = path.join(frontend, "src-tauri");
mkdirSync(path.join(tauri, "runtime"), { recursive: true });
writeFileSync(path.join(tauri, "runtime.json"), JSON.stringify({
  ...spec, root: mode === "dev" ? frontend : "",
  slug: config.slug, args: config.args, bootstrap: config.bootstrap ?? [],
}, null, 2));
