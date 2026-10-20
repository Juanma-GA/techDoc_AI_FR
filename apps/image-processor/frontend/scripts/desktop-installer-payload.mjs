import { execFileSync } from "node:child_process";
import { cpSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

const LOCAL_PROJECTS = new Set([
  "image-processor-backend",
  "image-processor-lama-service",
]);

function writeDependencyLock(python, runtime, filename) {
  const environment = { ...process.env };
  delete environment.PYTHONHOME;
  delete environment.PYTHONPATH;
  delete environment.PYTHONUSERBASE;
  environment.PYTHONNOUSERSITE = "1";
  const frozen = execFileSync(python, ["-m", "pip", "freeze", "--all"], {
    cwd: runtime,
    env: environment,
    encoding: "utf8",
  });
  const packages = frozen
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => {
      const name = line.split(/[=<>!~@ ]/, 1)[0].toLowerCase().replaceAll("_", "-");
      return !LOCAL_PROJECTS.has(name);
    });
  if (packages.length === 0) {
    throw new Error(`Could not create dependency lock: ${filename}`);
  }
  writeFileSync(path.join(runtime, filename), `${packages.join("\n")}\n`);
}

export function prepareInstallerPayload({ frontend, runtime, config, pythonApi, pythonLama, getPipUrl }) {
  writeDependencyLock(pythonApi, runtime, "requirements-api.lock");
  writeDependencyLock(pythonLama, runtime, "requirements-lama.lock");
  writeFileSync(
    path.join(runtime, "desktop-install.json"),
    `${JSON.stringify({
      python_versions: config.python_versions,
      get_pip_url: getPipUrl,
      model_cache: config.model_cache,
    }, null, 2)}\n`,
  );
  for (const name of ["install-desktop-runtime.ps1", "desktop-install-runtime-functions.ps1"]) {
    cpSync(path.join(frontend, "scripts", name), path.join(runtime, name));
  }
  rmSync(path.join(runtime, "python-ocr"), { recursive: true, force: true });
  rmSync(path.join(runtime, "python-lama"), { recursive: true, force: true });
}
