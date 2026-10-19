import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, needsBuild } from "../lib/frontend-build.mjs";
import { copySources, resolvePort } from "../lib/scaffold.mjs";
import { createPoc } from "../new_poc.mjs";

const repo = fileURLToPath(new URL("../../", import.meta.url));
function temporary(t) {
  const root = mkdtempSync(path.join(tmpdir(), "poc-tooling-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}
function write(root, name, text = "synthetic") {
  const file = path.join(root, name);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text);
  return file;
}

test("frontend rebuild includes shared UI, tokens, public assets and the root lockfile", (t) => {
  const root = temporary(t);
  const frontend = path.join(root, "apps", "synthetic", "frontend");
  const output = path.join(root, "bundle");
  const index = write(output, "index.html");
  const old = new Date(Date.now() - 120_000);
  const now = new Date();
  utimesSync(index, now, now);
  assert.equal(needsBuild(root, frontend, output), false);
  for (const file of ["packages/ui/src/Button.tsx", "design-tokens/theme.css",
    "pnpm-lock.yaml", "apps/synthetic/frontend/public/splash.html"]) {
    const source = write(root, file);
    const newer = new Date(now.getTime() + 10_000);
    utimesSync(source, newer, newer);
    assert.equal(needsBuild(root, frontend, output), true, file);
    utimesSync(source, old, old);
  }
  rmSync(index);
  assert.equal(needsBuild(root, frontend, output), true);
});

test("source copying excludes synthetic data, secrets and generated directories", (t) => {
  const root = temporary(t);
  const source = path.join(root, "source");
  for (const file of ["data/user.pdf", "storage/upload.pdf", ".env", "test.db",
    "node_modules/module.js", "dist/bundle.js", "target/file", "build/output",
    "fake.egg-info/PKG-INFO", "nested/.env.production"]) write(source, file);
  write(source, "app/main.py");
  write(source, ".env.example");
  const destination = path.join(root, "copy");
  copySources(source, destination);
  assert.equal(existsSync(path.join(destination, "app/main.py")), true);
  assert.equal(existsSync(path.join(destination, ".env.example")), true);
  for (const file of ["data", "storage", ".env", "test.db", "node_modules", "dist",
    "target", "build", "fake.egg-info", "nested/.env.production"]) {
    assert.equal(existsSync(path.join(destination, file)), false, file);
  }
});

test("a failed Vite build restores the entire previous bundle, never an empty success", (t) => {
  const root = temporary(t);
  const frontend = path.join(root, "frontend");
  const output = path.join(root, "bundle");
  const index = write(output, "index.html", "synthetic previous bundle");
  write(output, "assets/app.js", "synthetic previous asset");
  utimesSync(index, new Date(0), new Date(0));
  mkdirSync(path.join(frontend, "node_modules"), { recursive: true });
  write(frontend, "package.json", JSON.stringify({
    name: "synthetic-failed-build", scripts: { build: "node failed-build.cjs" },
  }));
  write(frontend, "failed-build.cjs",
    `const fs = require("node:fs"); fs.writeFileSync("build-executed", "yes"); ` +
    `fs.rmSync(${JSON.stringify(output)}, {recursive:true,force:true}); process.exit(1);`);
  buildFrontend(root, frontend, output, { allowStale: true });
  assert.equal(existsSync(path.join(frontend, "build-executed")), true);
  assert.equal(readFileSync(index, "utf8"), "synthetic previous bundle");
  assert.equal(readFileSync(path.join(output, "assets/app.js"), "utf8"), "synthetic previous asset");
  utimesSync(index, new Date(0), new Date(0));
  assert.throws(() => buildFrontend(root, frontend, output), /failed/);
  assert.equal(readFileSync(index, "utf8"), "synthetic previous bundle");
});

for (const desktop of [false, true]) {
  test(`scaffolds ${desktop ? "web + desktop" : "web-only"} without Python execution`, (t) => {
    const root = temporary(t);
    copySources(path.join(repo, "apps", "_template"), path.join(root, "apps", "_template"));
    write(root, "scripts/package_TEMPLATE.py", readFileSync(path.join(repo, "scripts/package_TEMPLATE.py"), "utf8"));
    write(root, "package.json", JSON.stringify({ scripts: {} }));
    createPoc({ repo: root, slug: "synthetic-test", port: 8123, desktop });
    const app = path.join(root, "apps", "synthetic-test");
    const pkg = JSON.parse(readFileSync(path.join(app, "frontend/package.json"), "utf8"));
    assert.equal(pkg.name, "@apps/synthetic-test-frontend");
    assert.equal(existsSync(path.join(app, "frontend/src-tauri/Cargo.toml")), desktop);
    assert.equal(existsSync(path.join(app, "desktop")), false);
    assert.equal(readFileSync(path.join(app, "_run.bat"), "utf8").includes('set "PORT=8123"'), true);
    assert.equal(readFileSync(path.join(root, "scripts/package_synthetic-test.py"), "utf8")
      .includes('APP_SLUG = "synthetic-test"'), true);
    const scripts = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).scripts;
    assert.equal(Boolean(scripts["desktop:dev:synthetic-test"]), desktop);
    if (desktop) {
      const config = JSON.parse(readFileSync(path.join(app, "frontend/desktop.json"), "utf8"));
      assert.equal(config.slug, "synthetic-test");
      assert.match(readFileSync(path.join(app, "frontend/src-tauri/tauri.conf.json"), "utf8"),
        /com\.atexis\.synthetic-test/);
    }
    assert.throws(() => createPoc({ repo: root, slug: "synthetic-test" }), /already exists/);
  });
}

test("validates slugs and port collisions without modifying the repository", (t) => {
  const root = temporary(t);
  write(root, "apps/_template/README.md");
  write(root, "apps/occupied/_run.bat", 'set "PORT=8000"');
  assert.equal(resolvePort(root), 8001);
  assert.throws(() => resolvePort(root, 8000), /assigned/);
  assert.throws(() => resolvePort(root, 65530), /Invalid port/);
  assert.throws(() => createPoc({ repo: root, slug: "../unsafe" }), /kebab-case/);
  assert.deepEqual(createPoc({ repo: root, slug: "safe", dryRun: true }),
    { slug: "safe", port: 8001, desktop: false });
  assert.equal(existsSync(path.join(root, "apps", "safe")), false);
});
