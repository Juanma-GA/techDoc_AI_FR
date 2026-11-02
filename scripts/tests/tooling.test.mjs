import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildFrontend, needsBuild } from "../lib/frontend-build.mjs";
import {
  expectedAppArtifacts,
  readAppRegistry,
  validateAppRegistry,
} from "../lib/app-registry.mjs";
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

function addRegistry(root, apps) {
  write(root, "docs/apps/README.md", "Inventory\n<!-- APP_REGISTRY_START -->\n<!-- APP_REGISTRY_END -->\n");
  write(root, "QUICK_START.md", "Quick start\n<!-- APP_REGISTRY_START -->\n<!-- APP_REGISTRY_END -->\n");
  return write(root, "scripts/apps.json", JSON.stringify({
    schemaVersion: 1,
    defaultProfiles: ["local-first"],
    profiles: ["local-first", "llm", "files"],
    apps,
  }));
}

function registryEntry(slug, targetPort, kind = "app") {
  return {
    slug,
    displayName: slug,
    kind,
    backend: "fastapi",
    targetPort,
    profiles: ["local-first"],
    desktop: false,
    e2e: false,
    openapi: false,
  };
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

test("app registry enforces unique ports, supported profiles and a single template", () => {
  const registry = {
    schemaVersion: 1,
    defaultProfiles: ["local-first"],
    profiles: ["local-first", "llm", "files"],
    apps: [registryEntry("_template", 8000, "template"), registryEntry("example", 8001)],
  };
  assert.doesNotThrow(() => validateAppRegistry(registry));
  assert.throws(
    () => validateAppRegistry({ ...registry, apps: [...registry.apps, registryEntry("duplicate", 8001)] }),
    /Duplicate target port/,
  );
  assert.throws(
    () => validateAppRegistry({
      ...registry,
      apps: [registry.apps[0], { ...registry.apps[1], profiles: ["local-first", "production"] }],
    }),
    /Unsupported profile/,
  );
  assert.equal(readAppRegistry(repo).schemaVersion, 1);
});

test("registry synchronization preserves CRLF in generated documentation", (t) => {
  const root = temporary(t);
  const crlf = (text) => text.replace(/\n/g, "\r\n");
  write(root, "package.json", JSON.stringify({ scripts: {} }));
  write(
    root,
    "docs/apps/README.md",
    crlf("# Inventory\n<!-- APP_REGISTRY_START -->\n<!-- APP_REGISTRY_END -->\n"),
  );
  write(
    root,
    "QUICK_START.md",
    crlf("# Quick start\n<!-- APP_REGISTRY_START -->\n<!-- APP_REGISTRY_END -->\n"),
  );
  write(root, "apps/_template/README.md", crlf("# Template\n\n## Auth\n\nLocal only.\n\n## Port\n\n8000.\n"));

  const registry = {
    schemaVersion: 1,
    defaultProfiles: ["local-first"],
    profiles: ["local-first", "llm", "files"],
    apps: [registryEntry("_template", 8000, "template")],
  };
  const artifacts = expectedAppArtifacts(root, registry);

  for (const relativePath of [
    "docs/apps/README.md",
    "QUICK_START.md",
    "apps/_template/README.md",
  ]) {
    const content = artifacts.get(path.join(root, relativePath));
    assert.ok(content?.includes("\r\n"), relativePath);
    assert.equal(content?.replace(/\r\n/g, "").includes("\n"), false, relativePath);
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
  for (const profiles of [undefined, ["llm"], ["files"]]) {
    test(`scaffolds ${profiles?.join("+") ?? "local-first"} ${desktop ? "desktop" : "web"} app`, (t) => {
      const root = temporary(t);
      copySources(path.join(repo, "apps", "_template"), path.join(root, "apps", "_template"));
      addRegistry(root, [registryEntry("_template", 8000, "template")]);
      write(root, "scripts/package_TEMPLATE.py", readFileSync(path.join(repo, "scripts/package_TEMPLATE.py"), "utf8"));
      write(root, "package.json", JSON.stringify({ scripts: {} }));
      const result = createPoc({ repo: root, slug: "synthetic-test", port: 8123, desktop, profiles });
      const app = path.join(root, "apps", "synthetic-test");
      const pkg = JSON.parse(readFileSync(path.join(app, "frontend/package.json"), "utf8"));
      const hasLlm = profiles?.includes("llm") ?? false;
      const readme = readFileSync(path.join(app, "README.md"), "utf8");
      const desktopPackage = readFileSync(path.join(app, "package-desktop.bat"), "utf8");
      const registry = JSON.parse(readFileSync(path.join(root, "scripts/apps.json"), "utf8"));

      assert.equal(pkg.name, "@apps/synthetic-test-frontend");
      assert.equal(existsSync(path.join(app, "frontend/src-tauri/Cargo.toml")), desktop);
      assert.match(desktopPackage, /_package\.bat" desktop/);
      assert.equal(readme.includes("package-desktop.bat"), desktop);
      assert.equal(existsSync(path.join(app, "desktop")), false);
      assert.equal(readFileSync(path.join(app, "_run.bat"), "utf8").includes('set "PORT=8123"'), true);
      assert.equal(readFileSync(path.join(root, "scripts/package_synthetic-test.py"), "utf8")
        .includes('APP_SLUG = "synthetic-test"'), true);
      assert.equal(existsSync(path.join(app, "backend/app/core/mistral_client.py")), hasLlm);
      assert.equal(readme.includes("- `local-first`"), true);
      assert.equal(readme.includes("## LLM Configuration"), hasLlm);
      assert.deepEqual(result.profiles, profiles?.includes("local-first")
        ? profiles
        : ["local-first", ...(profiles ?? [])]);
      assert.equal(registry.apps.at(-1).targetPort, 8123);
      assert.deepEqual(registry.apps.at(-1).profiles, result.profiles);
      assert.match(readFileSync(path.join(app, "frontend/index.html"), "utf8"),
        /<title>Synthetic Test<\/title>/);
      assert.equal(JSON.parse(readFileSync(path.join(app, "frontend/src/locales/fr.json"), "utf8"))
        .app.title, "Synthetic Test");
      const scripts = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).scripts;
      assert.equal(Boolean(scripts["desktop:dev:synthetic-test"]), desktop);
      assert.equal(Boolean(scripts["dev:synthetic-test"]), true);
      assert.equal(Boolean(scripts["test:e2e:synthetic-test"]), true);
      assert.equal(Boolean(scripts["openapi:gen:synthetic-test"]), true);
      if (hasLlm) {
        assert.match(readFileSync(path.join(app, "backend/app/config.py"), "utf8"),
          /mistral_chat_model: str = "mistral-medium-latest"/);
        assert.match(readFileSync(path.join(app, "backend/.env.example"), "utf8"),
          /MISTRAL_CHAT_MODEL=mistral-medium-latest/);
      } else {
        assert.doesNotMatch(readFileSync(path.join(app, "backend/app/config.py"), "utf8"), /mistral_/i);
        assert.doesNotMatch(readme, /Mistral|llm_enabled|LLM Configuration/);
      }
      if (desktop) {
        const config = JSON.parse(readFileSync(path.join(app, "frontend/desktop.json"), "utf8"));
        assert.equal(config.slug, "synthetic-test");
        const tauri = JSON.parse(readFileSync(path.join(app, "frontend/src-tauri/tauri.conf.json"), "utf8"));
        assert.equal(tauri.productName, "Synthetic Test");
        assert.match(tauri.identifier, /com\.atexis\.synthetic-test/);
        assert.equal(existsSync(path.join(app, "frontend/src/desktop-startup.tsx")), true);
        assert.match(readFileSync(path.join(app, "frontend/src/desktop-startup.html"), "utf8"),
          /<title>Synthetic Test<\/title>/);
        assert.match(readFileSync(path.join(app, "frontend/src/App.tsx"), "utf8"),
          /getCurrentWindow\?\.\(\)/);
        assert.match(readFileSync(path.join(app, "frontend/src/desktop-startup.html"), "utf8"),
          /setTheme\(theme\)/);
        const capability = JSON.parse(readFileSync(
          path.join(app, "frontend/src-tauri/capabilities/default.json"),
          "utf8",
        ));
        assert.deepEqual(capability.permissions, ["core:window:allow-set-theme"]);
        assert.deepEqual(capability.remote.urls, ["http://127.0.0.1:*"]);
      }
      assert.throws(() => createPoc({ repo: root, slug: "synthetic-test" }), /already exists/);
    });
  }
}

test("a failed standard validation rolls back the scaffold and synchronized files", (t) => {
  const root = temporary(t);
  copySources(path.join(repo, "apps", "_template"), path.join(root, "apps", "_template"));
  addRegistry(root, [registryEntry("_template", 8000, "template")]);
  write(root, "scripts/package_TEMPLATE.py", readFileSync(path.join(repo, "scripts/package_TEMPLATE.py"), "utf8"));
  write(root, "package.json", JSON.stringify({ scripts: {} }));
  const registryFile = path.join(root, "scripts/apps.json");
  const preservedFiles = [
    registryFile,
    path.join(root, "package.json"),
    path.join(root, "docs/apps/README.md"),
    path.join(root, "QUICK_START.md"),
    path.join(root, "apps/_template/README.md"),
    path.join(root, "apps/_template/frontend/src/locales/fr.json"),
  ];
  const originalContents = preservedFiles.map((file) => readFileSync(file));

  assert.throws(
    () => createPoc({
      repo: root,
      slug: "synthetic-failure",
      validate: () => { throw new Error("synthetic standard failure"); },
    }),
    /synthetic standard failure/,
  );

  assert.equal(existsSync(path.join(root, "apps/synthetic-failure")), false);
  assert.equal(existsSync(path.join(root, "scripts/package_synthetic-failure.py")), false);
  for (const [index, file] of preservedFiles.entries()) {
    assert.deepEqual(readFileSync(file), originalContents[index], path.relative(root, file));
  }
});

test("validates slugs and port collisions without modifying the repository", (t) => {
  const root = temporary(t);
  write(root, "apps/_template/README.md");
  addRegistry(root, [registryEntry("_template", 8000, "template"), registryEntry("occupied", 8001)]);
  assert.equal(resolvePort(root), 8002);
  assert.throws(() => resolvePort(root, 8001), /assigned/);
  assert.throws(() => resolvePort(root, 65530), /Invalid port/);
  assert.throws(() => createPoc({ repo: root, slug: "../unsafe" }), /kebab-case/);
  assert.deepEqual(createPoc({ repo: root, slug: "safe", dryRun: true }),
    { slug: "safe", port: 8002, desktop: false, profiles: ["local-first"] });
  assert.equal(existsSync(path.join(root, "apps", "safe")), false);
});
