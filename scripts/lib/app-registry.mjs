import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

export function readAppRegistry(repo) {
  const file = path.join(repo, "scripts", "apps.json");
  const registry = JSON.parse(readFileSync(file, "utf8"));
  validateAppRegistry(registry);
  return registry;
}

export function writeAppRegistry(repo, registry) {
  validateAppRegistry(registry);
  writeFileSync(
    path.join(repo, "scripts", "apps.json"),
    JSON.stringify(registry, null, 2) + "\n",
  );
}

export function validateAppRegistry(registry) {
  if (
    registry?.schemaVersion !== 1 ||
    !Array.isArray(registry.apps) ||
    !Array.isArray(registry.profiles) ||
    !registry.profiles.includes("local-first") ||
    !Array.isArray(registry.defaultProfiles) ||
    !registry.defaultProfiles.includes("local-first") ||
    registry.defaultProfiles.some((profile) => !registry.profiles.includes(profile))
  ) {
    throw new Error("Invalid app registry structure.");
  }

  const slugs = new Set();
  const ports = new Set();
  for (const app of registry.apps) {
    if (
      typeof app.slug !== "string" ||
      typeof app.displayName !== "string" ||
      !Number.isInteger(app.targetPort) ||
      app.targetPort < 1024 ||
      app.targetPort > 65515 ||
      !Array.isArray(app.profiles) ||
      !app.profiles.includes("local-first") ||
      typeof app.desktop !== "boolean" ||
      typeof app.e2e !== "boolean" ||
      typeof app.openapi !== "boolean"
    ) {
      throw new Error(`Invalid app registry entry: ${app?.slug ?? "(unknown)"}.`);
    }
    if (slugs.has(app.slug)) throw new Error(`Duplicate app slug: ${app.slug}.`);
    if (ports.has(app.targetPort)) throw new Error(`Duplicate target port: ${app.targetPort}.`);
    if (!["template", "app"].includes(app.kind)) {
      throw new Error(`Invalid app kind for ${app.slug}.`);
    }
    if (!["fastapi", "go"].includes(app.backend)) {
      throw new Error(`Unsupported backend stack for ${app.slug}.`);
    }
    if (app.profiles.some((profile) => !registry.profiles.includes(profile))) {
      throw new Error(`Unsupported profile declared for ${app.slug}.`);
    }
    slugs.add(app.slug);
    ports.add(app.targetPort);
  }

  if (registry.apps.filter((app) => app.kind === "template").length !== 1) {
    throw new Error("The app registry must contain exactly one template.");
  }
}

export function resolveTargetPort(registry, requested) {
  const usedPorts = new Set(registry.apps.map((app) => app.targetPort));
  let port = Number(requested ?? 8000);
  if (!Number.isInteger(port) || port < 1024 || port > 65515) {
    throw new Error("Invalid port (1024..65515).");
  }
  if (requested !== undefined && usedPorts.has(port)) {
    throw new Error(`Port ${port} is assigned to another app.`);
  }
  while (usedPorts.has(port) && port <= 8099) port++;
  if (requested === undefined && port > 8099) {
    throw new Error("No unassigned port in 8000..8099.");
  }
  return port;
}

export function normalizeProfiles(registry, requestedProfiles) {
  const requested = requestedProfiles ?? registry.defaultProfiles;
  if (!Array.isArray(requested) || requested.length === 0) {
    throw new Error("At least one supported profile is required.");
  }
  const profiles = [...new Set(requested)];
  if (profiles.some((profile) => !registry.profiles.includes(profile))) {
    throw new Error(`Unsupported profile. Choose from: ${registry.profiles.join(", ")}.`);
  }
  return ["local-first", ...profiles.filter((profile) => profile !== "local-first")];
}

function backendStartCommand(app) {
  if (app.backend === "go") {
    if (!app.backendCommand) throw new Error(`Missing Go dev command for ${app.slug}.`);
    return `cd apps/${app.slug}/backend && ${app.backendCommand}`;
  }
  return (
    `cd apps/${app.slug}/backend && python -m uvicorn app.main:app ` +
    `--reload --host 127.0.0.1 --port ${app.targetPort}`
  );
}

export function generatedRootScripts(registry) {
  const scripts = {};
  for (const app of registry.apps.filter((entry) => entry.kind === "app")) {
    scripts[`dev:${app.slug}`] =
      `concurrently -k -n back,front -c blue,green "${backendStartCommand(app)}" ` +
      `"pnpm --filter @apps/${app.slug}-frontend dev"`;
    if (app.e2e) {
      scripts[`test:e2e:${app.slug}`] =
        `pnpm --filter @apps/${app.slug}-frontend --if-present test:e2e`;
    }
    if (app.openapi) {
      scripts[`openapi:gen:${app.slug}`] =
        `pnpm --filter @apps/${app.slug}-frontend --if-present openapi:gen`;
    }
    if (app.desktop) {
      scripts[`desktop:dev:${app.slug}`] = `pnpm --filter @apps/${app.slug}-frontend tauri:dev`;
      scripts[`desktop:build:${app.slug}`] = `pnpm --filter @apps/${app.slug}-frontend tauri:build`;
    }
  }
  return scripts;
}

function putPortSurface(artifacts, file, transform) {
  if (!existsSync(file)) return;
  const current = readFileSync(file, "utf8");
  const expected = transform(current);
  if (expected !== current) artifacts.set(file, expected);
}

function updateAppPortSurfaces(repo, registry, artifacts) {
  for (const app of registry.apps) {
    const appRoot = path.join(repo, "apps", app.slug);
    putPortSurface(artifacts, path.join(appRoot, "_run.bat"), (text) =>
      text.replace(/(^set "PORT=)\d+(")/m, (_match, prefix, suffix) =>
        `${prefix}${app.targetPort}${suffix}`,
      ),
    );
    putPortSurface(artifacts, path.join(appRoot, "start.sh"), (text) =>
      text.replace(/(^PORT="\$\{PORT:-)\d+("\})/m, (_match, prefix, suffix) =>
        `${prefix}${app.targetPort}${suffix}`,
      ),
    );
    putPortSurface(artifacts, path.join(appRoot, "frontend", "vite.config.ts"), (text) =>
      text
        .replace(/(DEFAULT_BACKEND_PORT\s*=\s*)\d+/, (_match, prefix) =>
          `${prefix}${app.targetPort}`,
        )
        .replace(/(http:\/\/127\.0\.0\.1:)\d{4}/g, (_match, prefix) =>
          `${prefix}${app.targetPort}`,
        ),
    );
    putPortSurface(artifacts, path.join(appRoot, "frontend", "package.json"), (text) => {
      const manifest = JSON.parse(text);
      if (typeof manifest.scripts?.["openapi:gen"] === "string") {
        manifest.scripts["openapi:gen"] = manifest.scripts["openapi:gen"].replace(
          /(http:\/\/127\.0\.0\.1:)\d{4}/g,
          (_match, prefix) => `${prefix}${app.targetPort}`,
        );
      }
      return JSON.stringify(manifest, null, 2) + "\n";
    });

    for (const file of [
      path.join(appRoot, "backend", "app", "config.py"),
      path.join(appRoot, "backend", ".env.example"),
    ]) {
      putPortSurface(artifacts, file, (text) =>
        text
          .replace(/(http:\/\/(?:localhost|127\.0\.0\.1):)8\d{3}/g, (_match, prefix) =>
            `${prefix}${app.targetPort}`,
          )
          .replace(/(^\s*bind_port:\s*int\s*=\s*)\d+/m, (_match, prefix) =>
            `${prefix}${app.targetPort}`,
          )
          .replace(/(^BIND_PORT=)\d+/m, (_match, prefix) => `${prefix}${app.targetPort}`),
      );
    }

    putPortSurface(artifacts, path.join(appRoot, "frontend", ".env.example"), (text) =>
      text.replace(/(^VITE_BACKEND_PORT=)\d+/m, (_match, prefix) =>
        `${prefix}${app.targetPort}`,
      ),
    );
    putPortSurface(artifacts, path.join(appRoot, "README.md"), (text) => {
      const heading = text.search(/^## Port\s*$/m);
      if (heading < 0) return text;
      const nextHeading = text.indexOf("\n## ", heading + 1);
      const end = nextHeading < 0 ? text.length : nextHeading;
      const section = text.slice(heading, end);
      const updated = section.replace(
        /(target default port(?: is)?\s*`?)(\d+)(`?)/i,
        (_match, prefix, _oldPort, suffix) => `${prefix}${app.targetPort}${suffix}`,
      );
      return text.slice(0, heading) + updated + text.slice(end);
    });
  }
}

function replaceGeneratedBlock(content, startMarker, endMarker, replacement) {
  const start = content.indexOf(startMarker);
  const end = content.indexOf(endMarker);
  if (start < 0 || end < 0 || end < start) {
    throw new Error(`Missing or invalid generated block: ${startMarker}.`);
  }
  const newline = content.includes("\r\n") ? "\r\n" : "\n";
  const generated = replacement.replace(/\r?\n/g, newline);
  return (
    content.slice(0, start + startMarker.length) +
    `${newline}${generated}${newline}` +
    content.slice(end)
  );
}

function profileSection(app) {
  const entries = app.profiles.map((profile) => `- \`${profile}\``).join("\n");
  return `## Profiles\n\n<!-- APP_PROFILES_START -->\n${entries}\n<!-- APP_PROFILES_END -->`;
}

function nextHeadingIndex(content, start) {
  const match = /\r?\n## /g;
  match.lastIndex = start;
  return match.exec(content)?.index ?? -1;
}

function syncReadmeProfiles(content, app) {
  const newline = content.includes("\r\n") ? "\r\n" : "\n";
  const section = profileSection(app).replace(/\r?\n/g, newline);
  const existing = /^## Profiles\s*$/m.exec(content);
  if (existing) {
    const nextHeading = nextHeadingIndex(content, existing.index + existing[0].length);
    const end = nextHeading < 0 ? content.length : nextHeading;
    return `${content.slice(0, existing.index)}${section}${newline}${content.slice(end)}`;
  }

  const auth = /^## Auth\s*$/m.exec(content);
  if (auth) {
    const nextHeading = nextHeadingIndex(content, auth.index + auth[0].length);
    const insertion = nextHeading < 0 ? content.length : nextHeading;
    return (
      `${content.slice(0, insertion)}${newline}${newline}${section}` +
      `${newline}${newline}${content.slice(insertion)}`
    );
  }

  throw new Error(`README for ${app.slug} is missing the required Auth section.`);
}

function syncShellLocale(content, language, flatKeys) {
  const resources = JSON.parse(content);
  const defaults = language === "fr"
    ? {
        ariaLabel: "Navigation principale",
        themeToggle: "Changer de thème",
        languageSwitcher: "Langue",
        collapse: "Replier le menu",
        expand: "Déplier le menu",
      }
    : {
        ariaLabel: "Main navigation",
        themeToggle: "Switch theme",
        languageSwitcher: "Language",
        collapse: "Collapse menu",
        expand: "Expand menu",
      };

  if (flatKeys) {
    if (resources.nav && typeof resources.nav === "object" && !Array.isArray(resources.nav)) {
      for (const [key, value] of Object.entries(resources.nav)) {
        resources[`nav.${key}`] ??= value;
      }
      delete resources.nav;
    }
    for (const [key, value] of Object.entries(defaults)) {
      resources[`nav.${key}`] ??= value;
    }
  } else {
    resources.nav ??= {};
    for (const [key, value] of Object.entries(defaults)) {
      resources.nav[key] ??= value;
    }
  }
  return JSON.stringify(resources, null, 2) + "\n";
}

export function expectedAppArtifacts(repo, registry) {
  const manifestPath = path.join(repo, "package.json");
  const rootPackage = JSON.parse(readFileSync(manifestPath, "utf8"));
  const scripts = rootPackage.scripts ?? {};
  for (const key of Object.keys(scripts)) {
    const match = /^(?:dev|test:e2e|openapi:gen|desktop:dev|desktop:build):(.+)$/.exec(key);
    if (match && registry.apps.some((app) => app.kind === "app" && app.slug === match[1])) {
      delete scripts[key];
    }
  }
  Object.assign(scripts, generatedRootScripts(registry));
  rootPackage.scripts = scripts;

  let inventory = readFileSync(path.join(repo, "docs", "apps", "README.md"), "utf8");
  const inventoryRows = registry.apps.map((app) => {
    const pathPrefix = app.kind === "template" ? "../.." : "../..";
    const link = `[${app.slug}](${pathPrefix}/apps/${app.slug}/README.md)`;
    const profiles = app.profiles.map((profile) => `\`${profile}\``).join(", ");
    const desktop = app.desktop ? "Yes" : "No";
    return `| ${link} | ${app.backend} | ${profiles} | ${app.targetPort} | ${desktop} |`;
  }).join("\n");
  inventory = replaceGeneratedBlock(
    inventory,
    "<!-- APP_REGISTRY_START -->",
    "<!-- APP_REGISTRY_END -->",
    `| Application | Backend | Profiles | Target default port | Desktop |\n|---|---|---|---:|---:|\n${inventoryRows}`,
  );

  let quickStart = readFileSync(path.join(repo, "QUICK_START.md"), "utf8");
  const quickStartRows = registry.apps
    .filter((app) => app.kind === "app")
    .map((app) => {
      const link = `[${app.displayName}](apps/${app.slug}/README.md)`;
      return `| ${link} | ${app.targetPort} | \`apps\\${app.slug}\\start.bat\` | \`bash apps/${app.slug}/start.sh\` |`;
    })
    .join("\n");
  quickStart = replaceGeneratedBlock(
    quickStart,
    "<!-- APP_REGISTRY_START -->",
    "<!-- APP_REGISTRY_END -->",
    `| App | Port cible | Windows | Unix |\n|---|---:|---|---|\n${quickStartRows}`,
  );

  const artifacts = new Map([
    [manifestPath, JSON.stringify(rootPackage, null, 2) + "\n"],
    [path.join(repo, "docs", "apps", "README.md"), inventory],
    [path.join(repo, "QUICK_START.md"), quickStart],
  ]);
  for (const app of registry.apps) {
    const readme = path.join(repo, "apps", app.slug, "README.md");
    if (!existsSync(readme)) throw new Error(`README is missing for ${app.slug}.`);
    artifacts.set(readme, syncReadmeProfiles(readFileSync(readme, "utf8"), app));
    const i18nConfig = path.join(repo, "apps", app.slug, "frontend", "src", "i18n.ts");
    const flatLocaleKeys =
      existsSync(i18nConfig) && /keySeparator\s*:\s*false/.test(readFileSync(i18nConfig, "utf8"));
    for (const language of ["fr", "en"]) {
      const locale = path.join(
        repo,
        "apps",
        app.slug,
        "frontend",
        "src",
        "locales",
        `${language}.json`,
      );
      if (existsSync(locale)) {
        artifacts.set(locale, syncShellLocale(readFileSync(locale, "utf8"), language, flatLocaleKeys));
      }
    }
  }
  updateAppPortSurfaces(repo, registry, artifacts);
  return artifacts;
}

export function syncAppArtifacts(repo, registry = readAppRegistry(repo)) {
  for (const [file, content] of expectedAppArtifacts(repo, registry)) {
    writeFileSync(file, content);
  }
}

function sourceFiles(root, files = []) {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (
      entry.isDirectory() &&
      [".git", "node_modules", "dist", "build", "coverage", "data", "storage", "uploads"].includes(entry.name)
    ) {
      continue;
    }
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) sourceFiles(fullPath, files);
    else if (/\.(?:js|jsx|ts|tsx)$/.test(entry.name)) files.push(fullPath);
  }
  return files;
}

function checkSharedUiOwnership(repo, registry) {
  const issues = [];
  const localShellComponents = new Set([
    "Sidebar.jsx",
    "Sidebar.tsx",
    "LangSwitch.jsx",
    "LangSwitch.tsx",
    "ThemeToggleButton.jsx",
    "ThemeToggleButton.tsx",
    "ThemeToggle.jsx",
    "ThemeToggle.tsx",
    "ErrorBoundary.jsx",
    "ErrorBoundary.tsx",
  ]);

  for (const app of registry.apps) {
    const frontend = path.join(repo, "apps", app.slug, "frontend");
    const sourceRoot = path.join(frontend, "src");
    if (!existsSync(sourceRoot)) {
      issues.push(`apps/${app.slug}/frontend/src is missing`);
      continue;
    }
    const files = sourceFiles(sourceRoot);
    const frontendPackage = path.join(frontend, "package.json");
    if (!existsSync(frontendPackage)) {
      issues.push(`apps/${app.slug}/frontend/package.json is missing`);
    } else {
      const manifest = JSON.parse(readFileSync(frontendPackage, "utf8"));
      if (!manifest.dependencies?.["@internal/ui"]) {
        issues.push(`apps/${app.slug}/frontend must declare @internal/ui directly`);
      }
    }
    const shellImported = files.some((file) => {
      const content = readFileSync(file, "utf8");
      return /AppShell/.test(content) && /@internal\/ui/.test(content);
    });
    if (!shellImported) issues.push(`apps/${app.slug} does not use AppShell from @internal/ui`);
    const sharedNavigationIcons = files.some((file) => {
      const content = readFileSync(file, "utf8");
      return content.includes("SidebarNavContent") && content.includes("@internal/ui");
    });
    if (!sharedNavigationIcons) {
      issues.push(`apps/${app.slug} must render sidebar navigation with @internal/ui SidebarNavContent`);
    }
    const sharedLanguageSwitcher = files.some((file) => {
      const content = readFileSync(file, "utf8");
      return content.includes("LanguageSwitcher") && content.includes("@internal/ui");
    });
    if (!sharedLanguageSwitcher) {
      issues.push(`apps/${app.slug} must use the @internal/ui LanguageSwitcher`);
    }
    const sharedErrorBoundary = files.some((file) => {
      const content = readFileSync(file, "utf8");
      return content.includes("ErrorBoundary") && content.includes("@internal/ui");
    });
    if (!sharedErrorBoundary) {
      issues.push(`apps/${app.slug} must use the @internal/ui ErrorBoundary`);
    }

    const duplicates = files.filter((file) => localShellComponents.has(path.basename(file)));
    if (duplicates.length) {
      issues.push(
        `apps/${app.slug} has local shell controls that belong in @internal/ui: ${duplicates.map((file) => path.relative(repo, file)).join(", ")}`,
      );
    }
    for (const file of files.filter((entry) => /^LlmBadge\.(?:js|jsx|ts|tsx)$/.test(path.basename(entry)))) {
      const content = readFileSync(file, "utf8");
      if (!content.includes("LlmStatus") || !content.includes("@internal/ui")) {
        issues.push(`${path.relative(repo, file)} must delegate status rendering to @internal/ui LlmStatus`);
      }
    }
    if (existsSync(path.join(sourceRoot, "components", "ui"))) {
      issues.push(`apps/${app.slug} defines a local components/ui directory`);
    }
  }
  return issues;
}

export function checkAppArtifacts(repo, registry = readAppRegistry(repo)) {
  const mismatches = [];
  for (const [file, expected] of expectedAppArtifacts(repo, registry)) {
    const actual = readFileSync(file, "utf8");
    if (actual.replace(/\r\n/g, "\n") !== expected.replace(/\r\n/g, "\n")) {
      mismatches.push(path.relative(repo, file));
    }
  }
  return [...mismatches, ...checkSharedUiOwnership(repo, registry)];
}
