# OCR Vision

## Purpose

Run OCR and multimodal vision on images or PDFs, then extract structured table rows and export them for local capitalization workflows.

## Maturity

**Status:** To be confirmed. Existing functional claims were not revalidated during the documentation reorganization.

## Features

- Run OCR text extraction and multimodal description in parallel.
- Define reusable table templates and project tables.
- Extract multiple structured rows from a document.
- Extract embedded images and export CSV or XLSX results.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Port

The target default port is `8005`, followed by the next free port when needed. The current Unix launcher and development configuration use older defaults.

## Prerequisites

Python 3.11+, Node 20, pnpm 9, and a Mistral API key for OCR, vision, and structured extraction.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:ocr-vision` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores projects, templates, extracted rows, image metadata, and runtime configuration. Generated images remain under the gitignored `backend/data/storage/` tree.

## LLM Configuration

OCR, multimodal description, and table extraction use Mistral. Disabled or unreadable inputs return best-effort empty results rather than server failures.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:ocr-vision`. No tests were executed during this documentation change.

## Limitations

Extraction quality depends on document readability and table-template rules. Platform launcher defaults are not yet aligned.

## Standard Deviations

The export endpoint may write CSV or XLSX files to a caller-selected existing local directory. This is limited to the local-first tier and requires review before any exposed deployment.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
