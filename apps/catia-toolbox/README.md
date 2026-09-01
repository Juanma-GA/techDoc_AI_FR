# CATIA Toolbox

## Purpose

Prepare reviewable plans and scripts for CATIA and Composer document-structure workflows without performing destructive source operations automatically.

## Maturity

**Status:** To be confirmed. Existing pipeline claims were not revalidated during the documentation reorganization.

## Features

- Identify parts from nomenclature and delivery inputs.
- Compare imports and verify naming, depth, duplication, and structure rules.
- Prepare CATPart-to-Composer conversion plans.
- Plan SMGXML colorization, tree optimization, and part replacement.
- Produce CSV, script, macro, and visual simulation artifacts for user review.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Port

The target default port is `8004`, followed by the next free port when needed. The current Unix launcher uses a different default.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. Mistral is optional for optimization suggestions. CATIA, Composer, OneDrive, UNC shares, or local folders apply only to relevant workflows.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:catia-toolbox` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores imports, plans, checks, and runtime configuration under `backend/data/`. Generated plans remain subject to user review.

## LLM Configuration

Mistral may suggest tree grouping. Deterministic type and naming heuristics remain available when LLM use is disabled.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:catia-toolbox`. No tests were executed during this documentation change.

## Limitations

Generated scripts and macros are dry-run or review artifacts; execution in CATIA or Composer is outside the automatic POC workflow.

## Standard Deviations

- Metadata-only folder scanning may read directory structure outside `backend/data/storage/` because it is a core local workflow.
- Some UI styling remains app-specific instead of using only shared primitives.
- Windows and Unix launcher defaults are not yet aligned.

## Technical References

- [Detailed technical reference](../../docs/apps/catia-toolbox/technical-reference.md)
- [Repository technical standard](../../STANDARD_POC.md)
