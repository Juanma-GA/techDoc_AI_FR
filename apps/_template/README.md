# Canonical POC Template

## Purpose

Provide the required FastAPI and React/Vite foundation for a new local-first POC. Create applications with `scripts/new_poc.sh`; do not use an existing POC as a template.

## Maturity

**Status:** To be confirmed. This directory is a scaffold, not an instantiated application.

## Features

- Standard health, settings, admin statistics, and reset endpoints under `/api/v1/`.
- Runtime Mistral configuration through `AppConfig`.
- Normal/demo mode setting persisted through `AppConfig`, with a local synthetic scenario.
- AI4TECHDOC identity through the shared `@internal/ui` logo component.
- React/Vite frontend served by FastAPI at `/`.
- Windows and Unix launchers, conditional frontend rebuild, and Windows packaging wrappers.
- Optional Tauri desktop shell, selected with `node scripts/new_poc.mjs <slug> [port] --desktop`.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Profiles
- `local-first`
- `llm`

## Port

The target default port is `8000`. Launchers must select and display the next free port when it is unavailable. See the [application inventory](../../docs/apps/README.md).

## Prerequisites

- Python 3.11 or later.
- Node 20 and pnpm 9 for frontend development and builds.
- A Mistral API key only for features that use the LLM profile.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root:

```bash
pnpm install
pnpm dev:TEMPLATE
```

## Served Interface

FastAPI serves the built React application from `frontend/dist/` at `/`. If the bundle is absent and cannot be built, `/` returns HTTP 503; there is no standalone preview UI.

## Persistence

The local-first profile uses the gitignored SQLite file `backend/data/TEMPLATE.db`. `AppConfig` stores runtime configuration and is preserved by the standard admin reset convention.

## LLM Configuration

The scaffold provides runtime settings, health states, connection testing, and the global `llm_enabled` switch. An instantiated POC must document deterministic or empty-result behavior when LLM use is disabled.

## Tests

- Backend: run the declared pytest suite under `backend/tests/`.
- Demo-mode settings: `pytest -q tests/test_settings.py` from `backend/`.
- Shared demo UI: `pnpm --filter @internal/ui test` from the repository root.
- Frontend: add and run Vitest and Playwright coverage for the instantiated workflows.
- Repository: run `bash scripts/check_standard.sh` when Bash is available.

For scenario registration and the shared icon path, see the [frontend integration guide](frontend/README.md).

## Limitations

The template has no business workflow and must be completed after instantiation.
The optional FastAPI desktop adapter currently targets Windows x64; web mode remains
available on Windows and Unix. See the [desktop and stack guide](../../docs/standards/desktop-and-stacks.md)
for runtime preparation, custom backend adapters, packaging and lifecycle validation.

## Standard Deviations

None by default. Every instantiated POC must document its own deviations.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [New POC skill](../../.github/skills/new-poc/SKILL.md)
- [Application README template](../../docs/standards/app-readme-template.md)
