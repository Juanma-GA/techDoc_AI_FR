import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = fileURLToPath(new URL("../", import.meta.url));
const projectRoot = path.resolve(frontendDir, "..");
const backendDir = path.join(projectRoot, "backend");
const binaryDir = path.join(backendDir, "bin");
const binaryName = process.platform === "win32" ? "pdf-toolkit-backend.exe" : "pdf-toolkit-backend";

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell: process.platform === "win32" && command === "pnpm",
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

await mkdir(binaryDir, { recursive: true });
run("pnpm", ["build"], frontendDir);
run(
  "go",
  ["build", "-o", path.join(binaryDir, binaryName), "./cmd/pdf-toolkit"],
  backendDir,
);
