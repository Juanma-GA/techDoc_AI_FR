import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { packageDesktop } from "../package_pdf_toolkit_desktop.mjs";

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

test("desktop ZIP contains only the generated setup at its root and refuses overwrite", {
  skip: process.platform !== "win32",
}, (t) => {
  const { app, build } = fixture(t);
  const zip = packageDesktop(app, { build });
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  const result = spawnSync("powershell", ["-NoProfile", "-Command",
    "Add-Type -AssemblyName System.IO.Compression.FileSystem; " +
    `$zip=[IO.Compression.ZipFile]::OpenRead(${quote(zip)}); ` +
    "try { $zip.Entries | ForEach-Object { $_.FullName } } finally { $zip.Dispose() }"],
  { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "PDF Toolkit_1.0.0_x64-setup.exe");
  const before = readFileSync(zip);
  assert.throws(() => packageDesktop(app, { build: () => assert.fail("must not build") }), /already exists/);
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
