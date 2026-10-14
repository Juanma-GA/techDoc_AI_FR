# S1000D Extractor

## Purpose

Transform PDF or Word source documents into an S1000D XML structure constrained by the local Issue 4.1 and 4.2 XSDs through a reusable intermediate representation and configurable target rules.

## Maturity

**Status:** Generation is constrained and checked against local Issue 4.1 and 4.2 XSDs for descriptive, procedural, and IPD data modules. Issue 5.0 remains validation-only and is not a generation target.

## Features

- Parse PDF and DOCX into a common intermediate representation.
- Classify, segment, map, and resolve S1000D element candidates.
- Accept optional DMRL, CIR, BREX, and client-rule resources.
- Generate data-module and publication-module skeletons.
- Build issue/type-specific content models from the local XSDs and constrain generated elements, order, cardinality, attributes, and values.
- Collect XSD/mapping errors separately from provisional business fields that need confirmation.
- Keep XML and ZIP downloads available when generation reports XSD or mapping problems.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

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

## Demo Mode

Select Demo mode in Settings to preload `WEG-WMO.pdf`, `DMRL_v2.xlsx`, and
`dm_header_template.example.json` from `frontend/public/demo/` into the Migration
form. This only selects the files; upload and processing begin when you start
the migration.

## Persistence

SQLite stores projects, source metadata, intermediate structures, mappings, outputs, findings, and runtime configuration under `backend/data/`.

## LLM Configuration

Mistral supports context classification. Behavior with LLM disabled is not sufficiently documented and remains to be confirmed.

## Tests

Use synthetic fixtures with the backend pytest suite and the frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:s1000d-extractor`.

## Limitations

Generated XML remains an incomplete working skeleton until its listed provisional business fields are confirmed. Source structures without a supported mapping are omitted from the XML and reported; IPD catalogs currently receive only the minimum XSD-compatible provisional structure when no part records are available. Generated XML never uses `TODO` as a value.

## Standard Deviations

- Domain dependencies include PyMuPDF, python-docx, lxml, and openpyxl.
- Theme and language preferences may use browser storage; no authentication or business state may be stored there.
- Launcher defaults do not yet match the target application port.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
