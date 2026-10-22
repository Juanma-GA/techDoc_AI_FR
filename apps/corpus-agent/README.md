# Corpus Agent

## Purpose

Analyze multi-format technical document corpora, detect checklist findings, and support document-grounded chat.

## Maturity

**Status:** To be confirmed. Existing functional claims were not revalidated during the documentation reorganization.

## Features

- Upload and synchronize DOCX, XLSM, and PDF corpora.
- Parse, chunk, index, and deduplicate documents.
- Run editable checklist analysis through Mistral.
- Stream project analysis and grounded chat over SSE.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication in the local-first profile.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

## Port

The target default port is `8001`, followed by the next free port when needed. The current Unix and development defaults are known to differ and require a separate launcher correction.

## Prerequisites

Python 3.11+, Node 20, pnpm 9, and a Mistral API key for analysis and chat. Tesseract is optional for local OCR fallback.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:corpus-agent`.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores projects, document metadata, chunks, findings, chat sessions, and runtime configuration under the gitignored `backend/data/` directory.

## LLM Configuration

Analysis and chat are LLM-driven. When LLM use is disabled, those tasks return HTTP 200 with empty results; uploaded documents and deterministic repository operations remain available.

## Tests

Use the backend pytest suite and the frontend scripts declared in `frontend/package.json`. The repository also declares `test:e2e:corpus-agent`. No tests were executed during this documentation change.

## Limitations

OCR quality depends on source documents and optional local tooling.

## Standard Deviations

- Checklist analysis has no deterministic finding fallback because business rules remain editable and LLM-driven.
- App-specific page styling remains in the preview skin; the shared shell,
  navigation, theme/language controls, and LLM status use `@internal/ui`.
- Deployment-oriented hardening remains outside the local-first profile.

## Technical References

- [Deployment guide](DEPLOYMENT_GUIDE.md)
- [Historical app audit](AUDIT_2025-06-26.md)
- [Repository technical standard](../../STANDARD_POC.md)
