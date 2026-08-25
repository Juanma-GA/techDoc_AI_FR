# XML Proofreader

Local app for Subject Matter Experts (SMEs) to read, validate and annotate
structured content (**DITA 1.3** and **S1000D**) as if it were the final PDF —
while everything is stored behind the scenes as **Oxygen XML Author** review
comments inside the XML. The SME never has to understand XML: they see a
PDF-like document, select text, and add highlights and comments. Each
annotation is written into the XML as Oxygen processing instructions, so the
file round-trips losslessly with Oxygen and its review tooling.

Migrated from a standalone Tauri/portable-HTML app into this monorepo's
FastAPI + React POC standard ([`STANDARD_POC.md`](../../STANDARD_POC.md)).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`. The app has its own **local,
client-side-only** sign-in/register screen (`src/ui/auth/Login.tsx`) used
purely to tag annotations with an author name/email (Oxygen's
`oxy_comment_start author=…`); credentials are stored in browser storage only,
nothing is verified server-side. See "Écarts au standard" below.

## Quick start

Double-click `start.bat` (Windows) or run `bash start.sh` (Unix). It creates
the Python venv, installs backend deps, runs Alembic migrations, builds the
React frontend if needed, and opens `http://127.0.0.1:8007/`.

Dev mode (backend `--reload` + Vite dev server on 5173):

```bash
pnpm install
pnpm dev:xml-proofreader
```

## Features

- **WYSIWYG viewer** — DITA/S1000D rendered as a paginated, PDF-like document.
- **Annotate like a PDF** — select text → highlight or comment.
- **100% Oxygen-compatible** review markup (`oxy_comment_*`, `oxy_custom` highlights, `flag="done"`), foreign track-changes preserved untouched.
- **Non-destructive** — the original XML is the source of truth; annotations are spliced in at exact offsets.
- Ships as a normal web app here (see deviations below for what was dropped).

See `src/core/` (pure TS engine: `xml/` lossless parser, `render/` DITA→presentation model, `oxygen/` PI parse/serialize) and `docs/` in the original project for the full design (not copied into this POC; fetch from the source repo if needed).

## Architecture

- **Backend** — the generic POC scaffold (FastAPI + SQLAlchemy 2 + Alembic, `AppConfig` table only): `/api/v1/health`, `/api/v1/settings`, `/api/v1/admin/*`. The app itself makes **no backend calls** — it is fully client-side (loads/saves XML via the browser File System Access API), so these routes exist for standard compliance but are unused by the UI.
- **Frontend** — React 18 + Vite + Zustand, ported unchanged from the original app's `src/core`, `src/ports`, `src/adapters`, `src/ui`. The adapters layer already auto-detects its runtime (`isTauri()` checks `window.__TAURI__`) and falls back to the browser implementation — no code changes were needed to run it web-only.

## Écarts au standard

- **Tauri desktop shell dropped** — `src-tauri/` (Rust project), the `tauri` npm script/`@tauri-apps/cli` dependency, and the native file dialogs / in-place `.bak` save were removed. The app runs as a normal browser tab; file open/save uses the browser File System Access API (falls back to download/upload on browsers that don't support it), same as the original app's non-Tauri "portable" mode.
- **Portable single-HTML build dropped** — `vite-plugin-singlefile` and the `build:portable` mode were removed; only the standard `frontend/dist/` served by the backend remains.
- **Local pseudo-auth kept as-is (rule #8)** — the sign-in/register screen is retained because author identity is load-bearing for Oxygen comment attribution, not because this app needs a security boundary. It is **not** a real auth system: no server validates credentials, everything lives in browser storage. Documented here per STANDARD_POC.md's escape hatch rather than removed, to avoid breaking the annotation-attribution feature.
- **No i18n (rule #10)** — the original app has no i18next infrastructure and is English-only; none was added to avoid a large, risky rewrite of `src/ui/**`. A follow-up could wire `react-i18next` around the existing English strings.
- **LLM/Mistral (rule #6)** — not used. The app's own `LlmPort`/`McpPort` abstractions are for an in-progress "AI chat" feature that is Tauri-only in the original app (`adapters/tauri/TauriLlm.ts`) and stays unavailable in this web-only POC (`isAvailable()` returns false without `window.__TAURI__`). `AppConfig`/`/api/v1/settings` exist per the standard scaffold but hold no real key.
- **Design system (rule #3/#4)** — `src/ui/theme.css` colors are now bridged to `design-tokens/tokens.json` (`:root` = light, `.dark` = dark) with a `ThemeToggle` button in the top bar; fonts are Inter/JetBrains Mono/Orbitron. Highlight colors and the fixed-dark XML/code view keep their own values on purpose (highlighter pens and code views shouldn't shift with the app theme). Still no Tailwind/`@internal/ui` components — layout stays hand-rolled CSS, unlike the rest of the monorepo.

## Data

No SQLite domain data — documents are opened/saved directly from the SME's
disk via the browser. `backend/data/xml_proofreader.db` only holds the
generic `app_config` table (unused here).
