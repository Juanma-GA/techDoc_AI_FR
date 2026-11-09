import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { run } from "./frontend-build.mjs";

export function prepareDesktopIcons(frontend, repo) {
  const { color } = JSON.parse(readFileSync(
    path.join(repo, "framework", "design-tokens", "tokens.json"),
    "utf8",
  ));
  const icons = path.join(frontend, "src-tauri", "icons");
  mkdirSync(icons, { recursive: true });
  const source = path.join(icons, "source.svg");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">` +
    `<rect width="512" height="512" rx="96" fill="${color.bg.base}"/>` +
    `<path d="M96 352 192 128h64l96 224h-72l-16-48h-96l-16 48zm92-104h56l-28-80zM376 128h48v224h-48z"` +
    ` fill="${color.brand["blue-light"]}"/></svg>`;
  if (existsSync(source) && readFileSync(source, "utf8") === svg
    && existsSync(path.join(icons, "icon.ico")) && existsSync(path.join(icons, "icon.png"))) return;
  writeFileSync(source, svg);
  run("pnpm", ["exec", "tauri", "icon", "src-tauri/icons/source.svg", "--output", "src-tauri/icons"], frontend);
}
