import { existsSync, writeFileSync } from "node:fs";
import path from "node:path";
import { run } from "../../../../scripts/lib/frontend-build.mjs";

export function createRuntimeSpec(frontend, config, mode) {
  if (!["dev", "build"].includes(mode)) throw new Error("Expected dev or build.");
  const service = (name) => ({
    ...config.services[name][mode],
    args: config.services[name].args,
    health_path: config.services[name].health_path,
  });
  return {
    root: mode === "dev" ? frontend : "",
    slug: config.slug,
    api: service("api"),
    lama: service("lama"),
    bootstrap: config.bootstrap,
    model_cache: mode === "build" ? config.model_cache : null,
  };
}

function prepareDevelopmentEnvironment(project, version, markerName) {
  const app = path.dirname(project);
  const venv = path.join(project, ".venv");
  const python = path.join(venv, "Scripts", "python.exe");
  if (!existsSync(python)) {
    run("py", [`-${version}`, "-m", "venv", venv], app);
  }
  const [major, minor] = version.split(".");
  run(
    python,
    ["-c", `import sys; assert sys.version_info[:2] == (${major}, ${minor}), "Python ${version} is required"`],
    project,
  );

  const marker = path.join(venv, markerName);
  if (!existsSync(marker)) {
    run(python, ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], project);
    run(python, ["-m", "pip", "install", "--no-build-isolation", "-e", project], project);
    writeFileSync(marker, "");
  }
}

export function prepareDevelopmentRuntime(frontend) {
  const backend = path.resolve(frontend, "../backend");
  prepareDevelopmentEnvironment(
    backend,
    "3.13",
    ".image-processor-installed",
  );
  prepareDevelopmentEnvironment(
    path.join(backend, "lama_service"),
    "3.11",
    ".image-processor-lama-installed",
  );
}
