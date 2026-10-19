import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, run } from "./lib/frontend-build.mjs";
import { prepareEmbeddedGo, stageGoSources } from "./lib/go-package.mjs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const app = path.join(repo, "apps", "pdf-toolkit");
if (process.platform !== "win32") throw new Error("This entry point creates Windows packages.");
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--out")) {
  throw new Error("Usage: node scripts/package_pdf_toolkit.mjs [--out apps/pdf-toolkit/dist]");
}
const output = path.resolve(args[1] ?? path.join(app, "dist"));
if (output !== path.join(app, "dist")) throw new Error("Output must be apps/pdf-toolkit/dist.");
buildFrontend(repo, path.join(app, "frontend"), path.join(app, "backend", "web", "static", "generated"), {
  allowStale: true,
});
const { version } = JSON.parse(readFileSync(path.join(app, "frontend", "package.json"), "utf8"));
const name = `pdf-toolkit-go-embedded-v${version}-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}`;
mkdirSync(output, { recursive: true });
const zip = path.join(output, `${name}.zip`);
if (existsSync(zip)) throw new Error(`Package already exists; move it before rebuilding: ${zip}`);
const staging = mkdtempSync(path.join(tmpdir(), "pdf-toolkit-package-"));
try {
  const root = path.join(staging, name);
  const packagedApp = path.join(root, "apps", "pdf-toolkit");
  stageGoSources(app, packagedApp);
  process.stdout.write("[package] Staging installed Go toolchain and vendored dependencies...\n");
  const goVersion = prepareEmbeddedGo(app, root, packagedApp);
  mkdirSync(path.join(root, "design-tokens"));
  for (const file of ["tokens.json", "theme.css"]) {
    cpSync(path.join(repo, "design-tokens", file), path.join(root, "design-tokens", file));
  }
  writeFileSync(path.join(root, "start.bat"),
    '@echo off\r\ncall "%~dp0apps\\pdf-toolkit\\start.bat"\r\n', "ascii");
  writeFileSync(path.join(root, "LISEZ-MOI.txt"),
    "Extract the entire ZIP into a writable local folder, then open start.bat.\r\n" +
    `Bundled ${goVersion}, source, vendored dependencies and built UI. Windows x64.\r\n` +
    "No Go, Node or Python installation or network connection required.\r\n" +
    "First launch compiles locally and can take a few minutes. Later launches reuse the binary.\r\n" +
    "Local web app only. Ctrl+C in the console stops the server.\r\n" +
    "Go still produces an executable. If Windows Security blocks it, contact IT.\r\n" +
    "This package does not disable, exclude or bypass any security protection.\r\n", "ascii");
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  process.stdout.write("[package] Compressing Go distribution and sources...\n");
  run("powershell", ["-NoProfile", "-Command",
    "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; " +
    `[IO.Compression.ZipFile]::CreateFromDirectory(${quote(root)}, ${quote(zip)}, ` +
    "[IO.Compression.CompressionLevel]::Optimal, $true)"], repo);
  process.stdout.write(`[package] ${zip}\n`);
} finally {
  rmSync(staging, { recursive: true, force: true });
}
