import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { copySources, resolvePort, substituteTree } from "./lib/scaffold.mjs";

export function createPoc({ repo, slug, port: requested, desktop = false, dryRun = false }) {
  if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(slug) || slug === "template") {
    throw new Error("Slug must be kebab-case and cannot be 'template'.");
  }
  const template = path.join(repo, "apps", "_template");
  const app = path.join(repo, "apps", slug);
  const packageScript = path.join(repo, "scripts", `package_${slug}.py`);
  if (!existsSync(template)) throw new Error("Canonical template not found.");
  if (existsSync(app) || existsSync(packageScript)) throw new Error("App or packaging script already exists.");
  const port = resolvePort(repo, requested);
  if (dryRun) return { slug, port, desktop };
  const title = slug.split("-").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
  const rootManifest = path.join(repo, "package.json");
  const rootPackage = JSON.parse(readFileSync(rootManifest, "utf8"));
  try {
    copySources(template, app, ["desktop"]);
    if (desktop) {
      copySources(path.join(template, "desktop"), path.join(app, "frontend"));
      const manifest = path.join(app, "frontend", "package.json");
      const pkg = JSON.parse(readFileSync(manifest, "utf8"));
      Object.assign(pkg.scripts, {
        "tauri:dev": "tauri dev",
        "tauri:build": "tauri build",
      });
      pkg.devDependencies["@tauri-apps/cli"] = "^2.12.2";
      writeFileSync(manifest, JSON.stringify(pkg, null, 2) + "\n");
      rootPackage.scripts[`desktop:dev:${slug}`] = `pnpm --filter @apps/${slug}-frontend tauri:dev`;
      rootPackage.scripts[`desktop:build:${slug}`] = `pnpm --filter @apps/${slug}-frontend tauri:build`;
    }
    substituteTree(app, [
      ['"title": "TEMPLATE"', `"title": "${title}"`],
      ['"productName": "TEMPLATE"', `"productName": "${title}"`],
      ["<title>TEMPLATE</title>", `<title>${title}</title>`],
      ["<h1>TEMPLATE</h1>", `<h1>${title}</h1>`],
      ["TEMPLATE", slug], ["_template", slug], ["8000", String(port)],
    ]);
    const packaging = readFileSync(path.join(repo, "scripts", "package_TEMPLATE.py"), "utf8")
      .replaceAll('APP_NAME = "TEMPLATE"', `APP_NAME = "${title}"`)
      .replaceAll("TEMPLATE", slug).replaceAll('"_template"', `"${slug}"`)
      .replaceAll('EMBED_PREFIX = "template"', `EMBED_PREFIX = "${slug.replaceAll("-", "_")}"`);
    writeFileSync(packageScript, packaging);
    writeFileSync(path.join(app, "README.md"),
      `# ${title}\n\nGenerated from the canonical template. Complete the business documentation.\n\n` +
      `## Auth\n\nTier 1: local only, bind \`127.0.0.1\`, no authentication.\n\n` +
      `## Profiles\n- \`local-first\`\n- \`llm\`\n\n` +
      `## Stack\n\nFastAPI backend; React/Vite with @internal/ui. Default port: ${port}.\n\n` +
      `## Start\n\nWindows: \`start.bat\`. Unix: \`bash start.sh\`. Development: \`pnpm dev:${slug}\`.\n\n` +
      `## Package\n\nWindows web ZIP: \`package.bat\`, output in \`dist/\`.\n\n` +
      (desktop ? `## Desktop\n\nOptional Tauri: \`pnpm desktop:dev:${slug}\` or ` +
        `\`pnpm desktop:build:${slug}\` from the repository root. Windows packaging is supported; ` +
        `Rust, Visual Studio C++ tools and WebView2 are required. ` +
        `See [desktop guide](../../docs/standards/desktop-and-stacks.md).\n\n` : "") +
      `## Tests\n\nRun backend pytest, frontend typecheck, test, build and Playwright smoke tests.\n\n` +
      `## Standard Deviations\n\nNone by default. Document backend-specific deviations here.\n`);
    rootPackage.scripts[`dev:${slug}`] =
      `concurrently -k -n back,front -c blue,green "cd apps/${slug}/backend && python -m uvicorn ` +
      `app.main:app --reload --host 127.0.0.1 --port ${port}" ` +
      `"pnpm --filter @apps/${slug}-frontend dev"`;
    for (const name of ["test:e2e", "openapi:gen"]) {
      rootPackage.scripts[`${name}:${slug}`] = `pnpm --filter @apps/${slug}-frontend --if-present ${name}`;
    }
    writeFileSync(rootManifest, JSON.stringify(rootPackage, null, 2) + "\n");
  } catch (error) {
    // Only paths created by this invocation are rolled back, never existing apps.
    rmSync(app, { recursive: true, force: true });
    rmSync(packageScript, { force: true });
    throw error;
  }
  return { slug, port, desktop };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const desktop = args.includes("--desktop");
  const dryRun = args.includes("--dry-run");
  const positional = args.filter((arg) => !["--desktop", "--dry-run"].includes(arg));
  if (positional.length < 1 || positional.length > 2 || positional.some((arg) => arg.startsWith("--"))) {
    throw new Error("Usage: node scripts/new_poc.mjs <slug> [port] [--desktop] [--dry-run]");
  }
  const result = createPoc({
    repo: fileURLToPath(new URL("../", import.meta.url)),
    slug: positional[0], port: positional[1], desktop, dryRun,
  });
  process.stdout.write(`${dryRun ? "[plan]" : "[created]"} ${JSON.stringify(result)}\n`);
  if (!dryRun) process.stdout.write("Next: pnpm install; complete README; run bash scripts/check_standard.sh.\n");
}
