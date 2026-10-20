import {
  cpSync,
  mkdirSync,
  readdirSync,
  rmSync,
} from "node:fs";
import path from "node:path";
import { copySources } from "../../../../scripts/lib/scaffold.mjs";
import { GET_PIP_URL, preparePythonEnvironment } from "./desktop-python-cache.mjs";
import { prepareModelCache } from "./desktop-model-build-cache.mjs";
import { validateModelCache } from "./desktop-model-cache.mjs";
import { prepareInstallerPayload } from "./desktop-installer-payload.mjs";

function copyBackendSources(backend, runtime) {
  const destination = path.join(runtime, "backend");
  rmSync(destination, { recursive: true, force: true });
  mkdirSync(destination, { recursive: true });
  for (const name of ["app", "alembic", "lama_service"]) {
    copySources(path.join(backend, name), path.join(destination, name));
  }
  for (const name of ["alembic.ini", "pyproject.toml", "README.md"]) {
    cpSync(path.join(backend, name), path.join(destination, name));
  }
}

export async function prepareBundledRuntime(frontend, config) {
  const app = path.resolve(frontend, "..");
  const backend = path.join(app, "backend");
  const tauri = path.join(frontend, "src-tauri");
  const runtime = path.join(tauri, "runtime");
  const cache = path.join(app, "dist", ".cache", "desktop");
  const buildRuntime = path.join(cache, "build-runtime");
  mkdirSync(runtime, { recursive: true });
  mkdirSync(buildRuntime, { recursive: true });
  copyBackendSources(backend, buildRuntime);
  const pythonApi = await preparePythonEnvironment(
    cache,
    buildRuntime,
    "python-ocr",
    config.python_versions.api,
    ["../backend"],
    path.join(buildRuntime, "backend"),
  );
  const pythonLama = await preparePythonEnvironment(
    cache,
    buildRuntime,
    "python-lama",
    config.python_versions.lama,
    ["../backend/lama_service"],
    path.join(buildRuntime, "backend", "lama_service"),
  );
  await prepareModelCache(tauri, runtime, buildRuntime, config.model_cache, pythonApi, pythonLama);

  for (const entry of readdirSync(runtime)) {
    if (entry !== ".gitkeep") {
      rmSync(path.join(runtime, entry), { recursive: true, force: true });
    }
  }
  copyBackendSources(backend, runtime);
  cpSync(path.join(frontend, "dist"), path.join(runtime, "frontend", "dist"), { recursive: true });
  cpSync(path.join(buildRuntime, "models"), path.join(runtime, "models"), { recursive: true });
  validateModelCache(runtime, config.model_cache);
  prepareInstallerPayload({
    frontend,
    runtime,
    config,
    pythonApi,
    pythonLama,
    getPipUrl: GET_PIP_URL,
  });
}
