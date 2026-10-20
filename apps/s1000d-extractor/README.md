# S1000D Extractor

## Purpose

Transform PDF or Word source documents into a best-effort S1000D XML structure through a reusable intermediate representation and configurable target rules.

## Maturity

**Status:** To be confirmed. S1000D output validity and workflow claims were not revalidated during this documentation reorganization.

## Features

- Parse PDF and DOCX into a common intermediate representation.
- Classify, segment, map, and resolve S1000D element candidates.
- Accept optional DMRL, CIR, BREX, and client-rule resources.
- Generate data-module and publication-module skeletons.
- Collect XSD, BREX, metadata, and mapping validation findings.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

## Port

The target default port is `8006`, followed by the next free port when needed. Current Windows and Unix launchers still use `8004`, which also collides with another target assignment.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. Mistral is used for context classification. Client XSD, BREX, DMRL, and CIR inputs are optional workflow resources.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:s1000d-extractor` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores projects, source metadata, intermediate structures, mappings, outputs, findings, and runtime configuration under `backend/data/`.

## LLM Configuration

Mistral supports context classification. Behavior with LLM disabled is not sufficiently documented and remains to be confirmed.

## Tests

Use synthetic fixtures with the backend pytest suite and the frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:s1000d-extractor`. No tests were executed during this documentation change.

## Limitations

Generated XML is a best-effort skeleton. Client-specific identifiers, applicability, security, references, and media may remain explicit TODO items.

## Standard Deviations

- Domain dependencies include PyMuPDF, python-docx, lxml, and openpyxl.
- Theme and language preferences may use browser storage; no authentication or business state may be stored there.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
