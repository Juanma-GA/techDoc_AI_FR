import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

function containsFile(directory) {
  if (!existsSync(directory)) return false;
  return readdirSync(directory, { withFileTypes: true }).some((entry) => {
    const child = path.join(directory, entry.name);
    return entry.isFile() || (entry.isDirectory() && containsFile(child));
  });
}

function containsDirectory(directory, name) {
  if (!existsSync(directory)) return false;
  return readdirSync(directory, { withFileTypes: true }).some((entry) => {
    if (!entry.isDirectory()) return false;
    return entry.name.toLowerCase() === name.toLowerCase()
      || containsDirectory(path.join(directory, entry.name), name);
  });
}

export function validateModelCache(runtime, modelCache) {
  const paddleCache = path.resolve(runtime, modelCache.paddlex);
  const torchHome = path.resolve(runtime, modelCache.torch_home);
  for (const model of modelCache.ocr_models) {
    if (!containsDirectory(paddleCache, model)) {
      throw new Error(`Bundled PaddleOCR model is missing: ${model}`);
    }
  }
  if (!containsFile(paddleCache)) {
    throw new Error("Bundled PaddleOCR model cache is empty.");
  }
  const lamaCheckpoint = path.join(torchHome, "hub", "checkpoints", "big-lama.pt");
  if (!existsSync(lamaCheckpoint) || statSync(lamaCheckpoint).size === 0) {
    throw new Error("Bundled LaMa checkpoint is missing or empty.");
  }
}
