import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { run } from "../../../../scripts/lib/frontend-build.mjs";
import { isModelCacheValid, validateModelCache } from "./desktop-model-cache.mjs";
import { embeddedEnvironment } from "./desktop-python-cache.mjs";

function sameModelAssets(previous, current) {
  return previous
    && previous.ocr_model_variant === current.ocr_model_variant
    && previous.lama_model_url === current.lama_model_url
    && JSON.stringify(previous.ocr_models) === JSON.stringify(current.ocr_models);
}

function modelFingerprint(modelCache) {
  return createHash("sha256").update(JSON.stringify(modelCache)).digest("hex");
}

function migratePreviousModelCache(tauri, outputRuntime, buildRuntime, modelCache) {
  const specPath = path.join(tauri, "runtime.json");
  let previousCache = modelCache;
  if (existsSync(specPath)) {
    const configuredCache = JSON.parse(readFileSync(specPath, "utf8")).model_cache;
    if (configuredCache && !sameModelAssets(configuredCache, modelCache)) return false;
    if (configuredCache) previousCache = configuredCache;
  }

  for (const sourceRoot of [outputRuntime, path.join(outputRuntime, "runtime")]) {
    if (!isModelCacheValid(sourceRoot, previousCache)) continue;
    for (const key of ["paddlex", "torch_home"]) {
      const source = path.resolve(sourceRoot, previousCache[key]);
      const destination = path.resolve(buildRuntime, modelCache[key]);
      mkdirSync(path.dirname(destination), { recursive: true });
      cpSync(source, destination, { recursive: true });
    }
    if (isModelCacheValid(buildRuntime, modelCache)) return true;
    rmSync(path.join(buildRuntime, "models"), { recursive: true, force: true });
  }
  return false;
}

export async function prepareModelCache(
  tauri,
  outputRuntime,
  buildRuntime,
  modelCache,
  pythonApi,
  pythonLama,
) {
  const marker = path.join(buildRuntime, ".model-cache-fingerprint");
  const fingerprint = modelFingerprint(modelCache);
  let modelCacheReady = (
    existsSync(marker)
    && readFileSync(marker, "utf8").trim() === fingerprint
    && isModelCacheValid(buildRuntime, modelCache)
  );
  if (!modelCacheReady) {
    rmSync(path.join(buildRuntime, "models"), { recursive: true, force: true });
    modelCacheReady = migratePreviousModelCache(tauri, outputRuntime, buildRuntime, modelCache);
  }

  const smokeMarker = path.join(buildRuntime, ".model-smoke-fingerprint");
  const pythonFingerprint = [
    path.join(buildRuntime, "python-ocr", ".image-processor-build-fingerprint"),
    path.join(buildRuntime, "python-lama", ".image-processor-build-fingerprint"),
  ].map((file) => readFileSync(file, "utf8").trim()).join("\n");
  const runtimeInputs = [
    path.join(buildRuntime, "python-ocr"),
    path.join(buildRuntime, "python-lama"),
  ].map((directory) => {
    const pthFile = readdirSync(directory).find((entry) => /^python\d+\._pth$/.test(entry));
    if (!pthFile) throw new Error(`Missing embedded Python path file in ${directory}`);
    return readFileSync(path.join(directory, pthFile), "utf8");
  });
  runtimeInputs.push(
    readFileSync(path.join(buildRuntime, "backend", "app", "services", "ocr_inference.py"), "utf8"),
    readFileSync(path.join(buildRuntime, "backend", "lama_service", "app.py"), "utf8"),
  );
  const smokeFingerprint = createHash("sha256")
    .update([fingerprint, pythonFingerprint, ...runtimeInputs].join("\n"))
    .digest("hex");
  if (
    modelCacheReady
    && existsSync(smokeMarker)
    && readFileSync(smokeMarker, "utf8").trim() === smokeFingerprint
  ) {
    return;
  }

  const paddleCache = path.resolve(buildRuntime, modelCache.paddlex);
  const torchHome = path.resolve(buildRuntime, modelCache.torch_home);
  const buildHome = path.join(buildRuntime, "model-build-home");
  const preparationDatabase = path.join(buildRuntime, "build-preparation.db");
  const preparationStorage = path.join(buildRuntime, "build-preparation-storage");
  mkdirSync(paddleCache, { recursive: true });
  mkdirSync(torchHome, { recursive: true });
  mkdirSync(buildHome, { recursive: true });
  const modelEnvironment = embeddedEnvironment({
    DATABASE_URL: `sqlite:///${preparationDatabase.replaceAll("\\", "/")}`,
    STORAGE_DIR: preparationStorage,
    BIND_HOST: "127.0.0.1",
    HOME: buildHome,
    USERPROFILE: buildHome,
    OCR_MODEL_VARIANT: modelCache.ocr_model_variant,
    PADDLE_PDX_CACHE_HOME: paddleCache,
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK: "True",
    PADDLE_PDX_MODEL_SOURCE: "bos",
    TORCH_HOME: torchHome,
    LAMA_MODEL_URL: modelCache.lama_model_url,
  });
  try {
    if (!modelCacheReady) {
      mkdirSync(paddleCache, { recursive: true });
      mkdirSync(torchHome, { recursive: true });
    }
    run(
      pythonApi,
      ["-c", "from app.services.ocr_inference import get_ocr_engine; get_ocr_engine()"],
      path.join(buildRuntime, "backend"),
      modelEnvironment,
    );
    run(
      pythonLama,
      ["-c", "from simple_lama_inpainting import SimpleLama; SimpleLama()"],
      path.join(buildRuntime, "backend", "lama_service"),
      modelEnvironment,
    );
    validateModelCache(buildRuntime, modelCache);
    writeFileSync(marker, `${fingerprint}\n`);
    writeFileSync(smokeMarker, `${smokeFingerprint}\n`);
  } finally {
    rmSync(buildHome, { recursive: true, force: true });
    rmSync(preparationDatabase, { force: true });
    rmSync(preparationStorage, { recursive: true, force: true });
  }
}
