import { cpSync, existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export const excluded = new Set([
  "node_modules", ".venv", "__pycache__", "data", "storage", "uploads", "dist", "target",
  ".git", ".cache", ".pytest_cache", "coverage", "test-results", "playwright-report", "build",
]);

export function copySources(source, destination, extraExclusions = []) {
  cpSync(source, destination, {
    recursive: true,
    filter(file) {
      const parts = path.relative(source, file).split(path.sep);
      return !parts.some((part) => excluded.has(part) || extraExclusions.includes(part) || part.endsWith(".egg-info"))
        && !/\.(db|sqlite3?|pyc|log)$/i.test(file)
        && (!path.basename(file).startsWith(".env") || path.basename(file) === ".env.example");
    },
  });
}

export function substituteTree(root, replacements) {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const file = path.join(root, entry.name);
    if (entry.isDirectory()) substituteTree(file, replacements);
    else if (/\.(md|toml|ini|example|bat|sh|ps1|json|tsx?|mjs|js|html|css|py|rs)$/.test(file)) {
      let text = readFileSync(file, "utf8");
      for (const [from, to] of replacements) text = text.replaceAll(from, to);
      writeFileSync(file, text);
    }
  }
}

export function resolvePort(repo, requested) {
  const used = new Set();
  for (const name of readdirSync(path.join(repo, "apps"))) {
    if (name === "_template") continue;
    const file = path.join(repo, "apps", name, "_run.bat");
    if (!existsSync(file)) continue;
    const match = readFileSync(file, "utf8").match(/set "PORT=(\d+)"/);
    if (match) used.add(Number(match[1]));
  }
  let port = Number(requested ?? 8000);
  if (!Number.isInteger(port) || port < 1024 || port > 65515) throw new Error("Invalid port (1024..65515).");
  if (requested !== undefined && used.has(port)) throw new Error(`Port ${port} is assigned to another app.`);
  while (used.has(port) && port <= 8099) port++;
  if (requested === undefined && port > 8099) throw new Error("No unassigned port in 8000..8099.");
  return port;
}
