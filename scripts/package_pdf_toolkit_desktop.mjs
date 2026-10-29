import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { run } from "./lib/frontend-build.mjs";

const repo = fileURLToPath(new URL("../", import.meta.url));
const target = "x86_64-pc-windows-msvc";

export function buildTauri(app, runCommand = run) {
  const frontend = path.join(app, "frontend");
  if (!existsSync(path.join(frontend, "node_modules"))) runCommand("pnpm", ["install"], frontend);
  const buildEnv = { ...process.env, CARGO_TARGET_DIR: path.join(app, "dist", "tauri") };
  runCommand("cargo", ["clean"], path.join(frontend, "src-tauri"), buildEnv);
  runCommand("pnpm", ["tauri:build", "--bundles", "nsis", "--target", target, "--ci", "--", "--locked"],
    frontend, buildEnv);
}

export function packageDesktop(app, { build = buildTauri, now = new Date() } = {}) {
  if (process.platform !== "win32") throw new Error("This entry point creates Windows packages.");
  const frontend = path.join(app, "frontend");
  const config = JSON.parse(readFileSync(path.join(frontend, "src-tauri", "tauri.conf.json"), "utf8"));
  const { version } = JSON.parse(readFileSync(path.join(frontend, "package.json"), "utf8"));
  if (config.version !== version) throw new Error("Frontend and Tauri versions must match.");
  if (!/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(version)) throw new Error("Invalid package version.");
  if (!config.productName || /[<>:"/\\|?*\x00-\x1f]/.test(config.productName)) {
    throw new Error("Tauri productName must be a valid Windows file name.");
  }
  const output = path.join(app, "dist");
  const name = `pdf-toolkit-desktop-v${version}-${now.toISOString().slice(0, 10).replaceAll("-", "")}`;
  let suffix = 1;
  let zip;
  do {
    zip = path.join(output, `${name}${suffix === 1 ? "" : `-${suffix}`}.zip`);
    suffix += 1;
  } while (existsSync(zip));
  const started = Date.now();
  build(app);
  const installerName = `${config.productName}_${version}_x64-setup.exe`;
  const installer = path.join(output, "tauri", target, "release", "bundle", "nsis", installerName);
  if (!existsSync(installer)) throw new Error(`Tauri did not produce the expected installer: ${installer}`);
  const info = statSync(installer);
  if (!info.isFile() || info.size === 0 || info.mtimeMs < started - 2000) {
    throw new Error(`Tauri installer is empty or stale: ${installer}`);
  }
  const staging = mkdtempSync(path.join(tmpdir(), "pdf-toolkit-desktop-"));
  try {
    cpSync(installer, path.join(staging, installerName));
    mkdirSync(output, { recursive: true });
    const quote = (value) => `'${value.replaceAll("'", "''")}'`;
    run("powershell", ["-NoProfile", "-Command",
      "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; " +
      `[IO.Compression.ZipFile]::CreateFromDirectory(${quote(staging)}, ${quote(zip)}, ` +
      "[IO.Compression.CompressionLevel]::Optimal, $false)"], repo);
    process.stdout.write(`[package] Desktop installer ZIP: ${zip}\n`);
    return zip;
  } catch (error) {
    if (existsSync(zip)) rmSync(zip);
    throw error;
  } finally {
    rmSync(staging, { recursive: true, force: true });
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const app = path.join(repo, "apps", "pdf-toolkit");
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 2 || args[0] !== "--out")) {
    throw new Error("Usage: node scripts/package_pdf_toolkit_desktop.mjs [--out apps/pdf-toolkit/dist]");
  }
  if (path.resolve(args[1] ?? path.join(app, "dist")) !== path.join(app, "dist")) {
    throw new Error("Output must be apps/pdf-toolkit/dist.");
  }
  packageDesktop(app);
}
