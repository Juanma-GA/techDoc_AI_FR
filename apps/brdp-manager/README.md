# BRDP Manager

Business Rules Decision Points (BRDP) management for S1000D / DITA technical
documentation projects: import, validate, search/filter BRDP records, generate
BREX Data Modules and Schematron files, extract BRDPs from documents with AI,
and get expert guidance from an AI assistant.

Migrated from a standalone Node/Express + React app into this monorepo's
FastAPI + React POC standard ([`STANDARD_POC.md`](../../STANDARD_POC.md)).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

## Quick start

Double-click `start.bat` (Windows) or run `bash start.sh` (Unix). It creates the
Python venv, installs backend deps, runs Alembic migrations, builds the React
frontend if needed, and opens `http://127.0.0.1:8006/`.

Dev mode (backend `--reload` + Vite dev server on 5173):

```bash
pnpm install
pnpm dev:brdp-manager
```

## Features

- **BRDP records** — CRUD, search, filter by validation status, Excel import/export, per-record notes, edit history.
- **BREX / Schematron generation** — S1000D 4.2, S1000D 3.0.1, Schematron 1.0, streamed from Mistral, with guaranteed coverage of every validated BRDP.
- **AI Extract** — pull BRDPs out of a `.docx` / `.pdf` or pasted text, with duplicate detection before import.
- **AI Assistant** — a chat panel for S1000D / DITA questions, grounded in the current BRDP dataset.
- **Project configuration** — S1000D project metadata (model ident code, issue number, language/country, security classification…).

## Architecture

- **Backend** — FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic, SQLite at `backend/data/brdp_manager.db`. Endpoints: `/api/v1/brdps`, `/api/v1/notes/{id}`, `/api/v1/project-config`, `/api/v1/llm/chat` (+ `/stream`), `/api/v1/settings`, `/api/v1/admin/*`, `/api/v1/health`.
- **LLM** — Mistral API only (rule #6), key stored server-side via `AppConfig`/`core/mistral_client.py`. The original app's multi-provider support (Anthropic/OpenAI/Custom) and the Express `/api/proxy` were replaced by a single Mistral proxy; the client never sees the API key.
- **Frontend** — React 18 + Vite, ported from the original app with its component/page structure mostly intact (BREX/Schematron generators, AI Extract, Excel import/export, chat), adapted to call the new backend contract instead of `localStorage` + Express.

## Écarts au standard

- **Design system (rule #3/#4)** — colors are now bridged to `design-tokens/tokens.json` via `src/theme.css` (dual light/dark theme, fonts Inter/JetBrains Mono/Orbitron); components still use hand-written CSS Modules rather than `@internal/ui` primitives.
- **TypeScript strict (rule #1)** — pages/components were kept as `.jsx`/`.js` (not converted to `.tsx`) to preserve behavior during the port; `tsconfig.json` sets `allowJs: true, checkJs: false`. Converting to strict TS is a follow-up.
- **i18n (rule #10)** — `i18next` FR/EN is wired (`src/i18n.ts`, `src/locales/`) but only used by the app shell; the ported feature text remains in English (source strings), not yet keyed for translation.
- **Exported BREXdoc report** (`src/api/buildBREXdocReport.js`) generates a standalone printable HTML document (like a PDF/Word export) with its own fixed light color scheme, independent of the app's live theme — intentional, not a token-compliance gap.
- **Dependency install** — building the frontend requires `pnpm install` to reach the public npm registry. On a network with a TLS-intercepting proxy (e.g. Zscaler), this fails with `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` unless Node trusts that proxy's CA — export it and set `NODE_EXTRA_CA_CERTS` (see repo troubleshooting notes).

## Data

SQLite at `backend/data/brdp_manager.db`, created automatically by Alembic on
first run. Ten demo BRDPs (S1000D Issue 4.2) are seeded automatically when the
table is empty. Reset via **Data → Reset to demo data**, or `POST /api/v1/brdps/reset-demo`.
