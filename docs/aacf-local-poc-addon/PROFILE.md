# Local-First POC Application Profile

**Status:** Proposed; subject to the decisions in the package README.

## Applicability and Authority

Apply this profile only to a developer-only POC that runs on the developer's machine from the ATEXIS POC monorepo. It does not cover shared, client-facing, or production applications; use the applicable AACF template and tier controls for those projects.

This profile specifies local repository mechanics. It does not override AACF Hard Rules, security controls, governance, or the AACF design system. An unresolved policy conflict blocks adoption; a consuming project cannot grant itself an exception.

## Repository Organization

The monorepo owns one canonical scaffold and independent applications:

```text
apps/
  _template/
  <slug>/                 # one independent POC
    backend/              # FastAPI app, migrations, tests, local data
    frontend/             # React/Vite app and frontend tests
    start.bat
    _run.bat
    _needs_rebuild.ps1
    start.sh
    package.bat
    _package.bat
packages/ui/              # shared UI implementation
design-tokens/            # shared token implementation
scripts/                  # app creation, checks, and package scripts
```

- Instantiate a new app from `apps/_template/`, preferably with `scripts/new_poc.sh`; do not clone another POC.
- Keep business logic and app-specific UI in `apps/<slug>/`. Do not create runtime dependencies between POCs. Promote genuinely shared UI primitives to the shared UI package.
- Assign a unique default port and register the app's root development/test commands. Document the app's purpose, declared tier/profile, prerequisites, bind address, run commands, and deviations in its README.
- The scaffold is not complete merely because files exist: wire and test every screen and route required by the declared app profile.

## UI and UX Boundary

- The exact local UX and visual proposal (token values, typography, dimensions, components, app shell, screens, and states) is in [DESIGN.md](DESIGN.md). It is a proposed project profile, not an AACF-approved global design system.
- AACF remains the design authority. The workspace `design-tokens/` and `@internal/ui` may be used as adapters only after maintainers approve their mapping. Do not add per-app palettes, duplicate primitives, or competing design rules.
- Inherit AACF accessibility, localization, humanization, responsive behavior, and mutation requirements. Do not weaken HR1/HR15/HR20/HR21; resolve the open design decisions in `DESIGN.md` before adopting this profile.
- Serve the built React/Vite app at `/`; keep API routes ahead of the SPA fallback. Do not substitute an unbuilt preview UI. Report a visible build/start failure instead of implying that a stale bundle is current.

## Local Launchers

Every Windows-enabled POC provides a short `start.bat`, `_run.bat`, and `_needs_rebuild.ps1`; Unix-capable POCs also provide `start.sh`. The launchers are local execution tools, not deployment controls.

### Windows

- `start.bat` delegates to `_run.bat` in a `cmd /k` window so startup errors remain visible.
- Keep `.bat` files ASCII-only. Avoid unescaped parentheses in `echo` statements inside parenthesized `if` blocks.
- `_run.bat` resolves the app directory, prepares the supported Python environment and dependencies, runs database migrations, resolves a free port, checks/rebuilds the frontend, then starts the backend.
- Bind only to `127.0.0.1`. Try the assigned default port first; if occupied, select and print the next free port within the configured range before starting the server.
- Rebuild `frontend/dist/` when it is absent or stale. Use `_needs_rebuild.ps1` for timestamp comparison; do not rebuild on every restart.

### Dependencies and Frontend Build

- Run `pnpm install` only when `frontend/node_modules` is absent. When dependencies are already present, `pnpm build` should not require network access.
- If Node/pnpm is unavailable, serve an existing bundle only when the app's policy allows it. Never report the UI as freshly built after a failed build.
- Open the selected app root URL. Keep API documentation at its API docs route; do not use it as the default UI landing page.
- `start.sh` must match Windows port selection, loopback binding, build freshness, and app-root behavior. Verify parity rather than assuming the current scaffold implements it.

### Optional Packaging

- `package.bat` delegates through `_package.bat` to the app's package script.
- When packaging is required and approved, write the ZIP to `apps/<slug>/dist/`, not the repository root. Record the archive contents and verify that the packaged frontend bundle and launcher work.
- Packaging is not deployment and does not waive AACF security, release, or tier controls.

## Creation and Verification Workflow

1. Confirm that the project qualifies for this local-only profile and resolve the AACF adoption blockers.
2. Instantiate from the canonical scaffold; set the slug, unique port, app scripts, and README metadata.
3. Implement the backend and React workflows using approved shared UI/token artifacts; add only the capabilities the app declares.
4. Wire Home/Data/Settings only where applicable, plus the app's business routes. Test loading, empty, error, success, and destructive-action states.
5. Run the repository standard check, backend tests, frontend build/typecheck/tests, and critical-path browser smoke tests as applicable.
6. On Windows, verify startup on a free and occupied default port, visible error handling, correct app-root URL, and absent/stale frontend rebuild behavior. Verify Unix parity separately.
7. If packaging is in scope, verify the ZIP output path and launch the packaged app. Report checks run separately from checks not run.

Do not claim compliance based solely on this profile or on the local repository's standard-check script. AACF compliance requires the applicable current AACF rules and tier controls.
