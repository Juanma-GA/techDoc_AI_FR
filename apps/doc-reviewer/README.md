# Doc Reviewer

## Purpose

Detect technical-document anomalies, review proposed changes, and export annotated PDFs for an editorial validation workflow.

## Maturity

**Status:** To be confirmed. Runtime and conversion behavior were not revalidated during the documentation reorganization.

## Features

- Ingest PDF, DOCX, DOC, and supported ZIP inputs.
- Apply deterministic technical-writing catalogs, unit checks, editable rules, and optional LLM checklist analysis.
- Accept, edit, reject, and remember review decisions.
- Export PDF annotations and a review summary.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Port

The target default port is `8003`, followed by the next free port when needed. Older README and development configuration values used `8008` and remain a known configuration deviation.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. Mistral is optional for checklist rules. Word or LibreOffice is needed for supported Word-to-PDF conversions.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

Use the scripts declared in the root and frontend `package.json` files after confirming their backend port configuration.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores document versions, findings, review decisions, rejection memory, and runtime configuration under `backend/data/`.

## LLM Configuration

Mistral evaluates imported natural-language checklist rules. When disabled, deterministic catalogs, unit checks, and local rule paths remain available.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:doc-reviewer`. No tests were executed during this documentation change.

## Limitations

Word conversion fidelity depends on external office software. PDF editing is constrained by fonts, layout, signatures, and source text extraction.

## Standard Deviations

The current launcher, root development script, and older documentation do not yet share one default port.

## Technical References

- [Detailed technical reference](../../docs/apps/doc-reviewer/technical-reference.md)
- [Backend documentation](backend/README.md)
- [Repository technical standard](../../STANDARD_POC.md)
