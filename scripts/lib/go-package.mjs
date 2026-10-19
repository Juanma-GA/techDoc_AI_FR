import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { copySources } from "./scaffold.mjs";
import { run } from "./frontend-build.mjs";

export function stageGoSources(app, packagedApp) {
  mkdirSync(path.join(packagedApp, "backend"), { recursive: true });
  for (const name of ["cmd", "handlers", "services", "pdf", "web", "go.mod", "go.sum"]) {
    copySources(path.join(app, "backend", name), path.join(packagedApp, "backend", name));
  }
  for (const name of ["start.bat", "_run.bat", "_build_backend.ps1", "README.md", "LICENSE"]) {
    cpSync(path.join(app, name), path.join(packagedApp, name));
  }
}

export function stageGoToolchain(goroot, destination) {
  // Only the installed Go distribution, never module caches or user configuration.
  for (const name of ["bin/go.exe", "pkg/tool/windows_amd64/compile.exe", "src/runtime/runtime.go", "VERSION", "LICENSE"]) {
    if (!existsSync(path.join(goroot, name))) throw new Error(`Incomplete Windows x64 Go toolchain: ${name}`);
  }
  mkdirSync(destination, { recursive: true });
  for (const name of ["bin", "pkg", "src", "lib", "api", "VERSION", "go.env", "LICENSE", "PATENTS", "README.md", "SECURITY.md"]) {
    const source = path.join(goroot, name);
    if (existsSync(source)) cpSync(source, path.join(destination, name), { recursive: true });
  }
  return readFileSync(path.join(destination, "VERSION"), "utf8").split(/\r?\n/)[0];
}

export function prepareEmbeddedGo(app, root, packagedApp) {
  const settings = JSON.parse(execFileSync("go", ["env", "-json", "GOROOT", "GOHOSTOS", "GOHOSTARCH"], {
    encoding: "utf8",
  }));
  if (settings.GOHOSTOS !== "windows" || settings.GOHOSTARCH !== "amd64") {
    throw new Error("The embedded Go package currently requires a Windows x64 toolchain.");
  }
  const version = stageGoToolchain(settings.GOROOT, path.join(root, "go-embed"));
  const packagedBackend = path.join(packagedApp, "backend");
  run("go", ["mod", "vendor", "-o", path.join(packagedBackend, "vendor")], path.join(app, "backend"));
  writeFileSync(path.join(root, "GO_RUNTIME.json"), JSON.stringify({
    version, os: "windows", arch: "amd64", dependencies: "backend/vendor", networkRequired: false,
  }, null, 2) + "\n");
  return version;
}
