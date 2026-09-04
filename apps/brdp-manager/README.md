# BRDP Manager

## Purpose

Manage Business Rules Decision Points and generate reviewable S1000D BREX or Schematron outputs from validated records.

## Maturity

**Status:** To be confirmed. The migrated application and its generated outputs were not revalidated during the documentation reorganization.

## Features

- Create, search, filter, edit, and review BRDP records.
- Import and export spreadsheet records.
- Extract candidate rules from documents or pasted text.
- Generate S1000D 4.2, S1000D 3.0.1, and Schematron outputs.
- Provide a dataset-grounded AI assistant.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Port

The target default port is `8007`, followed by the next free port when needed. Current Windows, Unix, and root development defaults are not yet aligned with this target.

## Prerequisites

Python 3.11+, Node 20, pnpm 9, and a Mistral API key for extraction, chat, and generation.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:brdp-manager` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores BRDP records, project configuration, notes, history, runtime settings, and demo data under `backend/data/`.

## LLM Configuration

Mistral is the only supported provider. Behavior of extraction, chat, and generation when LLM use is disabled remains to be confirmed.

## Tests

Use only test commands declared by the backend and frontend manifests. No test or E2E command was confirmed or executed during this documentation change.

## Limitations

Generated BREX and Schematron content requires domain review. Frontend dependency installation may require the corporate proxy CA configuration.

## Standard Deviations

- Feature components retain CSS Modules instead of using only `@internal/ui`.
- Many components remain JSX with `allowJs` and without strict JS checking.
- Feature text is not yet fully localized.
- Launcher defaults do not yet match the target application port.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
