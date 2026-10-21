import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { run } from "../../../../scripts/lib/frontend-build.mjs";

export const GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py";

export function embeddedEnvironment(overrides = {}) {
  const environment = { ...process.env };
  delete environment.PYTHONHOME;
  delete environment.PYTHONPATH;
  delete environment.PYTHONUSERBASE;
  environment.PYTHONNOUSERSITE = "1";
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

function dependencyFingerprint(version, project) {
  return createHash("sha256")
    .update(`${version}\n${GET_PIP_URL}\n`)
    .update(readFileSync(path.join(project, "pyproject.toml")))
    .digest("hex");
}

export async function preparePythonEnvironment(cache, buildRuntime, name, version, importPaths, project) {
  const environment = path.join(buildRuntime, name);
  const python = path.join(environment, "python.exe");
  const marker = path.join(environment, ".image-processor-build-fingerprint");
  const fingerprint = dependencyFingerprint(version, project);
  const pthExists = existsSync(environment)
    && readdirSync(environment).some((entry) => /^python\d+\._pth$/.test(entry));
  if (
    existsSync(python)
    && existsSync(marker)
    && readFileSync(marker, "utf8").trim() === fingerprint
    && pthExists
  ) {
    pythonPathFile(environment, version, importPaths);
    return python;
  }
  rmSync(environment, { recursive: true, force: true });

  const archiveName = `python-${version}-embed-amd64.zip`;
  const archive = path.join(cache, archiveName);
  const getPip = path.join(cache, "get-pip.py");
  await download(`https://www.python.org/ftp/python/${version}/${archiveName}`, archive);
  await download(GET_PIP_URL, getPip);
  mkdirSync(environment, { recursive: true });
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  run(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath ${quote(archive)} -DestinationPath ${quote(environment)} -Force`,
    ],
    cache,
  );
  pythonPathFile(environment, version, importPaths);
  const pythonEnvironment = embeddedEnvironment();
  run(python, [getPip, "--no-warn-script-location"], environment, pythonEnvironment);
  run(
    python,
    ["-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--upgrade", "pip", "setuptools", "wheel"],
    environment,
    pythonEnvironment,
  );
  run(
    python,
    ["-m", "pip", "install", "--no-build-isolation", project],
    buildRuntime,
    pythonEnvironment,
  );
  writeFileSync(marker, `${fingerprint}\n`);
  return python;
}
