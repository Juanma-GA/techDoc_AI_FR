import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { copySources } from "./scaffold.mjs";
import { run } from "./frontend-build.mjs";

async function download(url, destination) {
  if (existsSync(destination)) return;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed (${response.status}): ${url}`);
  writeFileSync(destination, Buffer.from(await response.arrayBuffer()));
}

export async function prepareFastApi(frontend, mode) {
  if (process.platform !== "win32" || process.arch !== "x64") {
    throw new Error("The FastAPI desktop adapter currently supports Windows x64 only. Web remains cross-platform.");
  }
  const backend = path.resolve(frontend, "../backend");
  if (mode === "dev") {
    const python = path.join(backend, ".venv", "Scripts", "python.exe");
    if (!existsSync(python)) run("python", ["-m", "venv", path.join(backend, ".venv")], backend);
    const marker = path.join(backend, ".venv", ".desktop-installed");
    if (!existsSync(marker) || readFileSync(marker, "utf8") !== readFileSync(path.join(backend, "pyproject.toml"), "utf8")) {
      run(python, ["-m", "pip", "install", "-e", backend], backend);
      writeFileSync(marker, readFileSync(path.join(backend, "pyproject.toml")));
    }
    return;
  }
  const runtime = path.join(frontend, "src-tauri", "runtime");
  const cache = path.resolve(frontend, "../dist/.cache/desktop");
  mkdirSync(cache, { recursive: true });
  rmSync(runtime, { recursive: true, force: true });
  mkdirSync(runtime, { recursive: true });
  const archive = path.join(cache, "python-3.11.9-embed-amd64.zip");
  const getPip = path.join(cache, "get-pip.py");
  await download("https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip", archive);
  await download("https://bootstrap.pypa.io/get-pip.py", getPip);
  const pythonDir = path.join(runtime, "python");
  const quote = (value) => `'${value.replaceAll("'", "''")}'`;
  run("powershell", ["-NoProfile", "-Command",
    `$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath ${quote(archive)} -DestinationPath ${quote(pythonDir)} -Force`], frontend);
  // Import app from its source layout so FastAPI can locate sibling frontend/dist.
  writeFileSync(path.join(pythonDir, "python311._pth"),
    "python311.zip\n.\n../backend\nLib/site-packages\nimport site\n");
  const python = path.join(pythonDir, "python.exe");
  run(python, [getPip, "--no-warn-script-location"], frontend);
  run(python, ["-m", "pip", "install", backend], frontend);
  mkdirSync(path.join(runtime, "backend"));
  for (const name of ["app", "alembic", "alembic.ini", "pyproject.toml", "README.md"]) {
    copySources(path.join(backend, name), path.join(runtime, "backend", name));
  }
  cpSync(path.join(frontend, "dist"), path.join(runtime, "frontend", "dist"), { recursive: true });
}
