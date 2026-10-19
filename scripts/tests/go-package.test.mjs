import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import path from "node:path";
import { stageGoSources, stageGoToolchain } from "../lib/go-package.mjs";

function temporary(t) {
  const root = mkdtempSync(path.join(tmpdir(), "go-package-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}
function write(root, name, content = "synthetic") {
  const file = path.join(root, name);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, content);
}

test("Go package includes source and built UI, not a precompiled app, user data or secrets", (t) => {
  const root = temporary(t);
  const app = path.join(root, "app");
  for (const file of ["cmd/pdf-toolkit/main.go", "handlers/pdf.go", "services/pdf.go",
    "pdf/processor.go", "web/assets.go", "web/static/generated/index.html", "go.mod", "go.sum",
    "bin/pdf-toolkit-backend.exe", "data/private.pdf", "uploads/private.pdf", ".env"]) {
    write(path.join(app, "backend"), file);
  }
  for (const file of ["start.bat", "_run.bat", "_build_backend.ps1", "README.md", "LICENSE"]) write(app, file);
  const target = path.join(root, "package", "apps", "pdf-toolkit");
  stageGoSources(app, target);
  for (const file of ["cmd/pdf-toolkit/main.go", "web/static/generated/index.html", "go.mod", "go.sum"]) {
    assert.equal(existsSync(path.join(target, "backend", file)), true, file);
  }
  for (const file of ["bin", "data", "uploads", ".env"]) {
    assert.equal(existsSync(path.join(target, "backend", file)), false, file);
  }
  assert.equal(existsSync(path.join(target, "_build_backend.ps1")), true);
});

test("bundled toolchain includes compiler, standard library and license, not local caches", (t) => {
  const root = temporary(t);
  const source = path.join(root, "go");
  const target = path.join(root, "package", "go-embed");
  for (const file of ["bin/go.exe", "bin/gofmt.exe", "pkg/tool/windows_amd64/compile.exe",
    "src/runtime/runtime.go", "lib/time/zoneinfo.zip", "LICENSE", "go.env", "PATENTS", ".cache/private"]) write(source, file);
  write(source, "VERSION", "go1.27.2\ntime 2026-10-01\n");
  assert.equal(stageGoToolchain(source, target), "go1.27.2");
  assert.equal(existsSync(path.join(target, "pkg/tool/windows_amd64/compile.exe")), true);
  assert.equal(existsSync(path.join(target, "src/runtime/runtime.go")), true);
  assert.equal(existsSync(path.join(target, ".cache")), false);
  assert.equal(readFileSync(path.join(target, "LICENSE"), "utf8"), "synthetic");
});

test("rejects an incomplete or wrong-platform toolchain rather than generating a broken package", (t) => {
  const root = temporary(t);
  write(root, "go/bin/go.exe");
  assert.throws(() => stageGoToolchain(path.join(root, "go"), path.join(root, "package")),
    /Incomplete Windows x64 Go toolchain/);
  assert.equal(existsSync(path.join(root, "package")), false);
});

test("Windows launcher reuses an up-to-date binary without executing the compiler", {
  skip: process.platform !== "win32",
}, (t) => {
  const root = temporary(t);
  const app = path.join(root, "apps", "pdf-toolkit");
  for (const name of ["cmd", "handlers", "services", "pdf", "web", "vendor"]) {
    mkdirSync(path.join(app, "backend", name), { recursive: true });
  }
  for (const name of ["go.mod", "go.sum", "vendor/modules.txt", "web/static/generated/index.html"]) {
    write(path.join(app, "backend"), name);
  }
  write(root, "go-embed/bin/go.exe", "Not executable: this fixture must never be called.");
  write(root, "go-embed/VERSION", "go1.27.2");
  write(app, "backend/bin/pdf-toolkit-backend.exe", "synthetic cached binary");
  const binary = path.join(app, "backend", "bin", "pdf-toolkit-backend.exe");
  const future = new Date(Date.now() + 60_000);
  utimesSync(binary, future, future);
  const script = fileURLToPath(new URL("../../apps/pdf-toolkit/_build_backend.ps1", import.meta.url));
  const result = spawnSync("powershell", ["-NoProfile", "-File", script, "-AppDir", app], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /up to date/);
  assert.equal(readFileSync(binary, "utf8"), "synthetic cached binary");
});
