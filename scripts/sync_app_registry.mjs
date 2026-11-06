import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repo = fileURLToPath(new URL("../", import.meta.url));
const result = spawnSync(
  process.execPath,
  [path.join(repo, "framework", "scripts", "sync_app_registry.mjs"), "--repo-root", repo,
    ...process.argv.slice(2)],
  { cwd: repo, stdio: "inherit" },
);
if (result.error) throw result.error;
if (result.status !== 0) process.exitCode = result.status ?? 1;
