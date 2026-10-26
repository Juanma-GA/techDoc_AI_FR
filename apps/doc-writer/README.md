# Doc Writer

## Purpose

Generate technical content from selected source documents with retrieval-augmented generation and export the result in reusable formats.

## Maturity

**Status:** To be confirmed. Existing feature claims were not revalidated during this documentation reorganization.

## Features

- Parse PDF, DOCX, PPTX, XLSX, TXT, and Markdown sources.
- Build embeddings and stream cited RAG generation.
- Maintain multi-turn writing sessions.
- Export Markdown, DOCX, and PDF, or fill PPTX, DOCX, and PDF templates.
- Apply native-text, Mistral vision/OCR, and optional Tesseract extraction paths.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication by default (the only tier covered by the monorepo standard, CLAUDE.md rule #8).

**Écart documenté :** the codebase also contains a `TIER_MODE=tier2` / Azure deployment path (`deploy/azure/`), which is out of the POC standard's scope (palier 2/3). `_validate_security_posture()` in `backend/app/main.py` refuses to start (fail-fast `RuntimeError`) whenever `TIER_MODE=tier2` or `BIND_HOST` is not `127.0.0.1`/`localhost`/`::1`, **unless** the MFA pilot below is fully configured — so the app can never serve requests over an exposed bind while claiming auth is enforced but isn't.

**MFA pilot (R1, `settings.auth_enabled`) :** an auth path now exists, delegating login + MFA entirely to the corporate MS365 identity MCP service (same service consumed by KleamPy) and authorizing against a dedicated `docwriter_users` PostgreSQL table (own role mapping, no shared state with other apps). See `MFA_PILOT_CHECKLIST_DOC-WRITER_2026-09-14.md` (repo root) for full scope, status, and the infra prerequisites (a reachable Postgres instance, the internal CA bundle) still pending before this can be exercised end-to-end. Disabled by default (`auth_enabled=False`) — tier1 local behavior is completely unaffected until explicitly turned on via `.env`.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

## Port

The target default port is `8002`, followed by the next free port when needed.

## Prerequisites

Python 3.11+, Node 20, pnpm 9, and a Mistral API key for generation and embeddings. Tesseract, Word, or LibreOffice are optional for specific conversion paths.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:doc-writer`.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores source metadata, chunks, embeddings, writing sessions, generated content, templates, and runtime configuration under `backend/data/`.

## LLM Configuration

Runtime settings configure Mistral chat and embedding models. LLM-dependent generation is skipped when disabled; non-LLM document and session operations remain available.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:doc-writer`. No tests were executed during this documentation change.

## Limitations

PDF-to-DOCX conversion and scanned-document OCR are best effort. Template filling depends on identifiable placeholders or supported table structures.

## Standard Deviations

- `pdf2docx` and its transitive image-processing dependencies are required for PDF template filling.
- Tesseract is an optional external executable rather than a Python dependency.

## Technical References

- [Backend documentation](backend/README.md)
- [Repository technical standard](../../STANDARD_POC.md)
