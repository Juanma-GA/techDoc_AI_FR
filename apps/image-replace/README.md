# Image Replace

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Profiles

- `local-first`: the application runs locally and stores its current settings in SQLite.
- No `llm` profile: the planned image workflow uses local OCR and inpainting models, with no remote LLM or AI API.

## Purpose

Provide a local tool to find a supplied word or phrase in an image and replace it with supplied replacement text. The intended workflow uses PaddleOCR to locate text and LaMa to clean/inpaint the original image region.

## Maturity

**Status:** Scaffold only. The image upload, OCR, text replacement, and inpainting workflow has not yet been integrated or validated.

## Features

- Standard Home, Data, and Settings pages from the canonical template.
- Local normal/demo mode setting.
- Planned, not implemented: local OCR and replacement of user-selected text in an image using PaddleOCR and LaMa.

## Port

The target default port is `8010`. Launchers try this port first and select the next free port if needed. See the [application inventory](../../docs/apps/README.md).

## Prerequisites

- Python 3.11 or later.
- Node 20 and pnpm 9 for frontend development and builds.
- PaddleOCR and LaMa are not installed by this scaffold; their runtime requirements will be defined when the image workflow is integrated.

## Start On Windows

Double-click `start.bat`. The app opens at `http://127.0.0.1:8010/` unless the launcher selects another free port.

## Start On Unix

Run `bash start.sh`. The app opens at `http://127.0.0.1:8010/` unless the launcher selects another free port.

## Frontend Development

From the repository root:

```bash
pnpm install
pnpm dev:image-replace
```

Vite proxies `/api` requests to the backend on the app's assigned default port.

## Served Interface

FastAPI serves the built React application from `frontend/dist/` at `/`. If the bundle is absent, `/` returns HTTP 503 with build instructions; there is no standalone preview UI.

## Persistence

The app uses the gitignored SQLite database `backend/data/image-replace.db`. `AppConfig` currently stores the normal/demo mode preference. Image inputs and outputs are not yet handled or persisted.

## LLM Configuration

Not applicable. The scaffold does not call an LLM or any remote AI service. PaddleOCR recognition and LaMa inpainting are planned to run locally and have not yet been integrated.

## Tests

### Executed during bootstrap

- Backend: focused pytest suite, 3 tests passed.
- Frontend: TypeScript check, ESLint, Vitest (3 tests), and production build passed.
- Browser smoke: 1 Playwright test passed against the isolated Vite app; the backend was not running, so API integration was not exercised.
- Repository standard: all 16 checks passed using a temporary LF-normalized copy of `scripts/check_standard.sh`.
- Packaging CLI: `python -X utf8 scripts/package_image-replace.py --help` passed; no archive was produced.

### Recommended

- Add backend, frontend, and browser tests for image upload, local OCR, text replacement, and LaMa output when that workflow is integrated.
- Run the full packaging workflow after model runtime dependencies and distribution requirements are decided.

## Limitations

- The business workflow is not implemented.
- PaddleOCR and LaMa dependencies, model management, image handling, and output persistence remain to be designed during integration.
- No application-specific image-processing tests exist yet.

## Standard Deviations

None known. The app does not declare the `llm` profile.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application README template](../../docs/standards/app-readme-template.md)
- [Application inventory](../../docs/apps/README.md)
- [Canonical template](../_template/)
