import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRuntimeSpec } from "../../apps/image-processor/frontend/scripts/desktop-runtime.mjs";
import { validateModelCache } from "../../apps/image-processor/frontend/scripts/desktop-model-cache.mjs";

const app = path.resolve("apps/image-processor");
const frontend = path.join(app, "frontend");
const config = JSON.parse(readFileSync(path.join(frontend, "desktop.json"), "utf8"));
const frontendPackage = JSON.parse(readFileSync(path.join(frontend, "package.json"), "utf8"));

test("desktop runtime spec supervises both local services and bundles tiny model paths", () => {
  const spec = createRuntimeSpec(frontend, config, "build");
  assert.equal(spec.root, "");
  assert.equal(spec.slug, "image-processor");
  assert.match(spec.api.executable, /python-ocr/);
  assert.match(spec.lama.executable, /python-lama/);
  assert.equal(spec.api.health_path, "/api/v1/health");
  assert.equal(spec.lama.health_path, "/health");
  assert.equal(spec.model_cache.ocr_model_variant, "tiny");
  assert.equal(spec.model_cache.ocr_models.length, 3);
});

test("development runtime spec uses app venvs and does not override local model caches", () => {
  const spec = createRuntimeSpec(frontend, config, "dev");
  assert.match(spec.api.executable, /backend/);
  assert.match(spec.lama.executable, /lama_service/);
  assert.equal(spec.model_cache, null);
});

test("NSIS embeds the WebView2 offline installer", () => {
  const tauri = JSON.parse(readFileSync(path.join(frontend, "src-tauri/tauri.conf.json"), "utf8"));
  assert.ok(tauri.bundle.targets.includes("nsis"));
  assert.deepEqual(tauri.bundle.windows.webviewInstallMode, {
    type: "offlineInstaller",
    silent: true,
  });
});

test("Tauri commands prepare the desktop runtime before starting Cargo", () => {
  assert.equal(
    frontendPackage.scripts["tauri:dev"],
    "node scripts/prepare-desktop.mjs dev && tauri dev",
  );
  assert.equal(
    frontendPackage.scripts["tauri:build"],
    "node scripts/prepare-desktop.mjs build && tauri build",
  );
});

test("model cache validation requires all OCR model directories and the LaMa checkpoint", (t) => {
  const runtime = mkdtempSync(path.join(tmpdir(), "image-processor-models-"));
  t.after(() => rmSync(runtime, { recursive: true, force: true }));
  const cache = {
    paddlex: "models/paddlex",
    torch_home: "models/torch",
    ocr_models: ["PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec", "PP-LCNet_x1_0_textline_ori"],
  };
  assert.throws(() => validateModelCache(runtime, cache), /PaddleOCR model is missing/);

  for (const model of cache.ocr_models) {
    const directory = path.join(runtime, cache.paddlex, "official_models", model);
    mkdirSync(directory, { recursive: true });
    writeFileSync(path.join(directory, "model.bin"), "synthetic");
  }
  const checkpoint = path.join(runtime, cache.torch_home, "hub", "checkpoints", "big-lama.pt");
  mkdirSync(path.dirname(checkpoint), { recursive: true });
  writeFileSync(checkpoint, "synthetic");
  assert.doesNotThrow(() => validateModelCache(runtime, cache));
});
