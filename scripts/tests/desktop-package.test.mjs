import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { buildTauri, packageDesktop } from "../package_pdf_toolkit_desktop.mjs";

function fixture(t) {
  const app = mkdtempSync(path.join(tmpdir(), "desktop-package-test-"));
  t.after(() => rmSync(app, { recursive: true, force: true }));
  const frontend = path.join(app, "frontend");
  mkdirSync(path.join(frontend, "src-tauri"), { recursive: true });
  writeFileSync(path.join(frontend, "package.json"), JSON.stringify({ version: "1.0.0" }));
  writeFileSync(path.join(frontend, "src-tauri", "tauri.conf.json"),
    JSON.stringify({ productName: "PDF Toolkit", version: "1.0.0" }));
  const installer = path.join(app, "dist", "tauri", "x86_64-pc-windows-msvc",
    "release", "bundle", "nsis", "PDF Toolkit_1.0.0_x64-setup.exe");
  const build = () => {
    mkdirSync(path.dirname(installer), { recursive: true });
    writeFileSync(installer, "synthetic installer");
    writeFileSync(path.join(path.dirname(installer), "private.db"), "must not be packaged");
    writeFileSync(path.join(path.dirname(installer), ".env"), "must not be packaged");
  };
  return { app, installer, build };
}

test("desktop build cleans its dedicated Cargo target before building Tauri", (t) => {
  const { app } = fixture(t);
  const frontend = path.join(app, "frontend");
  mkdirSync(path.join(frontend, "node_modules"));
  const commands = [];

  buildTauri(app, (command, args, cwd, env) => commands.push({ command, args, cwd, env }));

  assert.deepEqual(commands.map(({ command, args, cwd }) => ({ command, args, cwd })), [
    { command: "cargo", args: ["clean"], cwd: path.join(frontend, "src-tauri") },
    {
      command: "pnpm",
      args: ["tauri:build", "--bundles", "nsis", "--target", "x86_64-pc-windows-msvc", "--ci", "--", "--locked"],
      cwd: frontend,
    },
  ]);
  assert.equal(commands[0].env.CARGO_TARGET_DIR, path.join(app, "dist", "tauri"));
  assert.equal(commands[1].env.CARGO_TARGET_DIR, path.join(app, "dist", "tauri"));
});

test("desktop ZIP contains only the generated setup and repeated packages preserve earlier ZIPs", {
  skip: process.platform !== "win32",
}, (t) => {
  const { app, build } = fixture(t);
  const now = new Date("2026-10-27T12:00:00.000Z");
  const zip = packageDesktop(app, { build, now });
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  const result = spawnSync("powershell", ["-NoProfile", "-Command",
    "Add-Type -AssemblyName System.IO.Compression.FileSystem; " +
    `$zip=[IO.Compression.ZipFile]::OpenRead(${quote(zip)}); ` +
    "try { $zip.Entries | ForEach-Object { $_.FullName } } finally { $zip.Dispose() }"],
  { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "PDF Toolkit_1.0.0_x64-setup.exe");
  const before = readFileSync(zip);
  const nextZip = packageDesktop(app, { build, now });
  assert.equal(nextZip, path.join(app, "dist", "pdf-toolkit-desktop-v1.0.0-20261027-2.zip"));
  assert.equal(existsSync(nextZip), true);
  assert.deepEqual(readFileSync(zip), before);
});

test("desktop packaging rejects missing, empty and stale installers", {
  skip: process.platform !== "win32",
}, (t) => {
  const { app, installer, build } = fixture(t);
  assert.throws(() => packageDesktop(app, { build: () => {} }), /expected installer/);
  assert.throws(() => packageDesktop(app, { build: () => {
    build();
    writeFileSync(installer, "");
  } }), /empty or stale/);
  assert.throws(() => packageDesktop(app, { build: () => {
    build();
    utimesSync(installer, new Date(0), new Date(0));
  } }), /empty or stale/);
});

test("a failed desktop build never packages an older installer", {
  skip: process.platform !== "win32",
}, (t) => {
  const { app, build } = fixture(t);
  build();
  assert.throws(() => packageDesktop(app, { build: () => { throw new Error("build failed"); } }), /build failed/);
  const name = `pdf-toolkit-desktop-v1.0.0-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}.zip`;
  assert.equal(existsSync(path.join(app, "dist", name)), false);
});
