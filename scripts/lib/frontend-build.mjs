import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

export function run(command, args, cwd, env = process.env) {
  const result = spawnSync(command, args, {
    cwd, env, stdio: "inherit",
    shell: process.platform === "win32" && command === "pnpm",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.signal})`);
}

export function sourceFiles(root) {
  if (!existsSync(root)) return [];
  if (statSync(root).isFile()) return [root];
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    if (["node_modules", "dist", "target", ".git"].includes(entry.name)) return [];
    const file = path.join(root, entry.name);
    return entry.isDirectory() ? sourceFiles(file) : entry.isFile() ? [file] : [];
  });
}

export function frontendSources(repo, frontend) {
  return [
    ...["src", "public", "index.html", "package.json", "tsconfig.json", "vite.config.ts",
      "tailwind.config.ts", "postcss.config.js"].map((name) => path.join(frontend, name)),
    path.join(repo, "framework", "packages", "ui", "src"),
    path.join(repo, "framework", "design-tokens"),
    path.join(repo, "packages", "techdoc-brand", "src"),
    path.join(repo, "pnpm-lock.yaml"), path.join(repo, "pnpm-workspace.yaml"),
    path.join(repo, "tsconfig.base.json"),
  ].flatMap(sourceFiles);
}

export function needsBuild(repo, frontend, output) {
  const index = path.join(output, "index.html");
  return !existsSync(index) || frontendSources(repo, frontend)
    .some((file) => statSync(file).mtimeMs > statSync(index).mtimeMs);
}

export function buildFrontend(repo, frontend, output, { allowStale = false } = {}) {
  if (!needsBuild(repo, frontend, output)) {
    process.stdout.write("[frontend] Bundle up to date.\n");
    return;
  }
  const hasBundle = existsSync(path.join(output, "index.html"));
  const backup = hasBundle ? mkdtempSync(path.join(tmpdir(), "poc-frontend-")) : null;
  if (backup) cpSync(output, path.join(backup, "bundle"), { recursive: true });
  try {
    if (!existsSync(path.join(frontend, "node_modules"))) run("pnpm", ["install"], frontend);
    run("pnpm", ["build"], frontend);
    if (!existsSync(path.join(output, "index.html"))) throw new Error(`Missing bundle: ${output}`);
  } catch (error) {
    if (backup) {
      rmSync(output, { recursive: true, force: true });
      cpSync(path.join(backup, "bundle"), output, { recursive: true });
    }
    if (!allowStale || !hasBundle) throw error;
    process.stderr.write(`[warning] ${error.message}; preserving the previous frontend bundle.\n`);
  } finally {
    if (backup) rmSync(backup, { recursive: true, force: true });
  }
}
