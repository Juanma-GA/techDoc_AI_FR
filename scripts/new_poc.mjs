import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  expectedAppArtifacts,
  normalizeProfiles,
  readAppRegistry,
  syncAppArtifacts,
  writeAppRegistry,
} from "./lib/app-registry.mjs";
import { copySources, resolvePort, substituteTree } from "./lib/scaffold.mjs";

function appReadme({ title, slug, port, profiles, desktop }) {
  const profileList = profiles.map((profile) => `- \`${profile}\``).join("\n");
  const llmSection = profiles.includes("llm")
    ? `## LLM Configuration\n\nThe app uses the LLM profile. Document the Mistral settings, ` +
      `the \`llm_enabled\` switch, and deterministic behavior when the LLM is disabled.\n\n`
    : "";
  const filesSection = profiles.includes("files")
    ? `## File Handling\n\nDocument accepted formats, size/MIME validation, storage, hashing, and versioning.\n\n`
    : "";
  const desktopSection = desktop
    ? `## Desktop\n\nOptional Tauri: \`pnpm desktop:dev:${slug}\` or ` +
      `\`pnpm desktop:build:${slug}\` from the repository root. ` +
      `See [desktop guide](../../docs/standards/desktop-and-stacks.md).\n\n`
    : "";

  return (
    `# ${title}\n\n` +
    `Generated from the canonical scaffold. Complete the business-specific sections before use.\n\n` +
    `## Purpose\n\nDescribe the business problem and intended users.\n\n` +
    `## Maturity\n\nStatus: To be confirmed. Record what has been validated.\n\n` +
    `## Features\n\nList the app-specific workflows.\n\n` +
    `## Auth\n\nTier 1: local only, bind \`127.0.0.1\`, no authentication.\n\n` +
    `## Profiles\n\n${profileList}\n\n` +
    `## Port\n\nThe target default port is \`${port}\`; launchers select the next free port when needed. ` +
    `See the [app inventory](../../docs/apps/README.md).\n\n` +
    `## Prerequisites\n\nPython 3.11+, Node 20 and pnpm 9. Add app-specific prerequisites.\n\n` +
    `## Start On Windows\n\nRun \`start.bat\`.\n\n` +
    `## Start On Unix\n\nRun \`bash start.sh\`.\n\n` +
    `## Frontend Development\n\nUse \`pnpm dev:${slug}\` from the repository root.\n\n` +
    `## Served Interface\n\nFastAPI serves the built React UI from \`frontend/dist/\` at \`/\`.\n\n` +
    `## Persistence\n\nDocument app-owned persistence and reset behavior.\n\n` +
    llmSection +
    filesSection +
    `## Tests\n\nList executed and recommended backend, frontend, browser, standard and package checks.\n\n` +
    `## Limitations\n\nList known limitations.\n\n` +
    `## Standard Deviations\n\nNone by default. Document approved deviations here.\n\n` +
    `## Technical References\n\nLink app-specific architecture notes and relevant ADRs.\n\n` +
    desktopSection
  );
}

function snapshotFiles(files) {
  return new Map(files.map((file) => [file, existsSync(file) ? readFileSync(file) : null]));
}

function restoreFiles(backups) {
  for (const [file, content] of backups) {
    if (content === null) rmSync(file, { force: true });
    else writeFileSync(file, content);
  }
}

function runStandardCheck(repo) {
  const result = spawnSync("bash", ["scripts/check_standard.sh"], {
    cwd: repo,
    stdio: "inherit",
  });
  if (result.error?.code === "ENOENT") {
    process.stderr.write(
      "Bash unavailable; scaffold validation was skipped. Run bash scripts/check_standard.sh before use.\n",
    );
    return;
  }
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error("Standard validation failed; scaffold and synchronized files were rolled back.");
  }
}

export function createPoc({
  repo,
  slug,
  port: requested,
  profiles: requestedProfiles,
  desktop = false,
  dryRun = false,
  validate,
}) {
  if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(slug) || slug === "template") {
    throw new Error("Slug must be kebab-case and cannot be 'template'.");
  }
  const registry = readAppRegistry(repo);
  const profiles = normalizeProfiles(registry, requestedProfiles);
  const template = path.join(repo, "apps", "_template");
  const app = path.join(repo, "apps", slug);
  const packageScript = path.join(repo, "scripts", `package_${slug}.py`);
  if (!existsSync(template)) throw new Error("Canonical template not found.");
  if (
    existsSync(app) ||
    existsSync(packageScript) ||
    registry.apps.some((entry) => entry.slug === slug)
  ) {
    throw new Error("App or packaging script already exists.");
  }
  const port = resolvePort(repo, requested);
  if (dryRun) return { slug, port, desktop, profiles };

  const title = slug.split("-").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
  const registryFile = path.join(repo, "scripts", "apps.json");
  const backups = snapshotFiles([...expectedAppArtifacts(repo, registry).keys(), registryFile]);
  try {
    copySources(template, app, ["desktop", "profiles"]);
    if (desktop) {
      copySources(path.join(template, "desktop"), path.join(app, "frontend"));
      const manifest = path.join(app, "frontend", "package.json");
      const pkg = JSON.parse(readFileSync(manifest, "utf8"));
      Object.assign(pkg.scripts, {
        "tauri:dev": "node scripts/prepare-desktop.mjs dev && tauri dev",
        "tauri:build": "node scripts/prepare-desktop.mjs build && tauri build",
      });
      pkg.devDependencies["@tauri-apps/cli"] = "^2.12.2";
      writeFileSync(manifest, JSON.stringify(pkg, null, 2) + "\n");
    }
    if (profiles.includes("llm")) {
      copySources(path.join(template, "profiles", "llm"), app);
    }

    substituteTree(app, [
      ['"title": "TEMPLATE"', `"title": "${title}"`],
      ['"productName": "TEMPLATE"', `"productName": "${title}"`],
      ["<title>TEMPLATE</title>", `<title>${title}</title>`],
      ["<h1>TEMPLATE</h1>", `<h1>${title}</h1>`],
      ["TEMPLATE", slug],
      ["_template", slug],
      ["8000", String(port)],
    ]);

    const packaging = readFileSync(path.join(repo, "scripts", "package_TEMPLATE.py"), "utf8")
      .replaceAll('APP_NAME = "TEMPLATE"', `APP_NAME = "${title}"`)
      .replaceAll("TEMPLATE", slug)
      .replaceAll('"_template"', `"${slug}"`)
      .replaceAll('EMBED_PREFIX = "template"', `EMBED_PREFIX = "${slug.replaceAll("-", "_")}"`);
    writeFileSync(packageScript, packaging);
    writeFileSync(
      path.join(app, "README.md"),
      appReadme({ title, slug, port, profiles, desktop }),
    );

    const appEntry = {
      slug,
      displayName: title,
      kind: "app",
      backend: "fastapi",
      targetPort: port,
      profiles,
      desktop,
      e2e: true,
      openapi: true,
    };
    const updatedRegistry = { ...registry, apps: [...registry.apps, appEntry] };
    writeAppRegistry(repo, updatedRegistry);
    syncAppArtifacts(repo, updatedRegistry);
    validate?.(repo);
  } catch (error) {
    rmSync(app, { recursive: true, force: true });
    rmSync(packageScript, { force: true });
    restoreFiles(backups);
    throw error;
  }

  return { slug, port, desktop, profiles };
}

function parseArgs(args) {
  const positional = [];
  const profiles = [];
  let desktop = false;
  let dryRun = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--desktop") desktop = true;
    else if (arg === "--dry-run") dryRun = true;
    else if (arg === "--profile") {
      const profile = args[index + 1];
      if (!profile || profile.startsWith("--")) throw new Error("--profile requires a value.");
      profiles.push(profile);
      index += 1;
    } else if (arg.startsWith("--profile=")) {
      profiles.push(arg.slice("--profile=".length));
    } else if (arg.startsWith("--")) {
      throw new Error(`Unknown option: ${arg}`);
    } else {
      positional.push(arg);
    }
  }

  if (positional.length < 1 || positional.length > 2) {
    throw new Error(
      "Usage: node scripts/new_poc.mjs <slug> [port] [--profile llm] [--profile files] [--desktop] [--dry-run]",
    );
  }
  return {
    slug: positional[0],
    port: positional[1],
    profiles: profiles.length ? profiles : undefined,
    desktop,
    dryRun,
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = parseArgs(process.argv.slice(2));
  const result = createPoc({
    repo: fileURLToPath(new URL("../", import.meta.url)),
    validate: args.dryRun ? undefined : runStandardCheck,
    ...args,
  });
  process.stdout.write(`${args.dryRun ? "[plan]" : "[created]"} ${JSON.stringify(result)}\n`);
  if (!args.dryRun) {
    process.stdout.write("Next: pnpm install; complete the business README and app-specific workflows.\n");
  }
}
