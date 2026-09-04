# Canonical POC Template

## Purpose

Provide the required FastAPI and React/Vite foundation for a new local-first POC. Create applications with `scripts/new_poc.sh`; do not use an existing POC as a template.

## Maturity

**Status:** To be confirmed. This directory is a scaffold, not an instantiated application.

## Features

- Standard health, settings, admin statistics, and reset endpoints under `/api/v1/`.
- Runtime Mistral configuration through `AppConfig`.
- React/Vite frontend served by FastAPI at `/`.
- Windows and Unix launchers, conditional frontend rebuild, and Windows packaging wrappers.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

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
- Frontend: add and run Vitest and Playwright coverage for the instantiated workflows.
- Repository: run `bash scripts/check_standard.sh` when Bash is available.

No test command was executed during the documentation reorganization.

## Limitations

The template has no business workflow and must be completed after instantiation.

## Standard Deviations

None by default. Every instantiated POC must document its own deviations.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [New POC skill](../../.github/skills/new-poc/SKILL.md)
- [Application README template](../../docs/standards/app-readme-template.md)
