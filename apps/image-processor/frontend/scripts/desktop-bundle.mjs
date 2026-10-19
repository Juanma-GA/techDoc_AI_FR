import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { copySources } from "../../../../scripts/lib/scaffold.mjs";
import { run } from "../../../../scripts/lib/frontend-build.mjs";
import { validateModelCache } from "./desktop-model-cache.mjs";

const PYTHON_VERSIONS = {
  api: "3.13.15",
  lama: "3.11.9",
};
const GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py";

function embeddedEnvironment(overrides = {}) {
  const environment = { ...process.env };
  delete environment.PYTHONHOME;
  delete environment.PYTHONPATH;
  return { ...environment, ...overrides };
}

async function download(url, destination) {
  if (existsSync(destination)) {
    if (statSync(destination).size > 0) return;
    rmSync(destination);
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed (${response.status}): ${url}`);
  const temporary = `${destination}.partial`;
  try {
    writeFileSync(temporary, Buffer.from(await response.arrayBuffer()));
    renameSync(temporary, destination);
  } catch (error) {
    rmSync(temporary, { force: true });
    throw error;
  }
}

function pythonPathFile(directory, version, importPaths) {
  const pth = readdirSync(directory).find((name) => /^python\d+\._pth$/.test(name));
  if (!pth) throw new Error(`Missing embedded Python path file in ${directory}`);
  const [major, minor] = version.split(".");
  writeFileSync(
    path.join(directory, pth),
    [`python${major}${minor}.zip`, ".", ...importPaths, "Lib/site-packages", "import site", ""].join("\n"),
  );
  mkdirSync(path.join(directory, "Lib", "site-packages"), { recursive: true });
}

async function prepareEmbeddedPython(cache, runtimeDir, version, importPaths) {
  const archiveName = `python-${version}-embed-amd64.zip`;
  const archive = path.join(cache, archiveName);
  const getPip = path.join(cache, "get-pip.py");
  await download(`https://www.python.org/ftp/python/${version}/${archiveName}`, archive);
  await download(GET_PIP_URL, getPip);

  mkdirSync(runtimeDir, { recursive: true });
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  run(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath ${quote(archive)} -DestinationPath ${quote(runtimeDir)} -Force`,
    ],
    cache,
  );
  pythonPathFile(runtimeDir, version, importPaths);
  const python = path.join(runtimeDir, "python.exe");
  const environment = embeddedEnvironment();
  run(python, [getPip, "--no-warn-script-location"], runtimeDir, environment);
  run(
    python,
    ["-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--upgrade", "pip", "setuptools", "wheel"],
    runtimeDir,
    environment,
  );
  return python;
}

function copyBackendSources(backend, runtime) {
  const destination = path.join(runtime, "backend");
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
  const backendRuntime = path.join(runtime, "backend");
  const pythonApiDir = path.join(runtime, "python-ocr");
  const pythonLamaDir = path.join(runtime, "python-lama");
  mkdirSync(runtime, { recursive: true });
  for (const entry of readdirSync(runtime)) {
    if (entry !== ".gitkeep") {
      rmSync(path.join(runtime, entry), { recursive: true, force: true });
    }
  }
  mkdirSync(cache, { recursive: true });

  const pythonApi = await prepareEmbeddedPython(
    cache,
    pythonApiDir,
    PYTHON_VERSIONS.api,
    ["../backend"],
  );
  const pythonLama = await prepareEmbeddedPython(
    cache,
    pythonLamaDir,
    PYTHON_VERSIONS.lama,
    ["../backend/lama_service", "../backend"],
  );
  copyBackendSources(backend, runtime);
  cpSync(path.join(frontend, "dist"), path.join(runtime, "frontend", "dist"), { recursive: true });

  const pythonEnv = embeddedEnvironment();
  run(pythonApi, ["-m", "pip", "install", "--no-build-isolation", backend], app, pythonEnv);
  run(
    pythonLama,
    ["-m", "pip", "install", "--no-build-isolation", path.join(backend, "lama_service")],
    app,
    pythonEnv,
  );

  const paddleCache = path.resolve(runtime, config.model_cache.paddlex);
  const torchHome = path.resolve(runtime, config.model_cache.torch_home);
  const buildHome = path.join(runtime, "models", "build-home");
  const preparationDatabase = path.join(runtime, "build-preparation.db");
  const preparationStorage = path.join(runtime, "build-preparation-storage");
  mkdirSync(paddleCache, { recursive: true });
  mkdirSync(torchHome, { recursive: true });
  mkdirSync(buildHome, { recursive: true });
  const modelEnv = embeddedEnvironment({
    DATABASE_URL: `sqlite:///${preparationDatabase.replaceAll("\\", "/")}`,
    STORAGE_DIR: preparationStorage,
    BIND_HOST: "127.0.0.1",
    HOME: buildHome,
    USERPROFILE: buildHome,
    OCR_MODEL_VARIANT: config.model_cache.ocr_model_variant,
    PADDLE_PDX_CACHE_HOME: paddleCache,
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK: "True",
    PADDLE_PDX_MODEL_SOURCE: "bos",
    TORCH_HOME: torchHome,
    LAMA_MODEL_URL: config.model_cache.lama_model_url,
  });
  run(
    pythonApi,
    ["-c", "from app.services.ocr_inference import get_ocr_engine; get_ocr_engine()"],
    backendRuntime,
    modelEnv,
  );
  run(
    pythonLama,
    ["-c", "from simple_lama_inpainting import SimpleLama; SimpleLama()"],
    path.join(backendRuntime, "lama_service"),
    modelEnv,
  );
  validateModelCache(runtime, config.model_cache);
  rmSync(buildHome, { recursive: true, force: true });
  rmSync(preparationDatabase, { force: true });
  rmSync(preparationStorage, { recursive: true, force: true });
}
