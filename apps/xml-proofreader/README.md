# XML Proofreader

## Purpose

Give subject-matter experts a paginated document view for DITA and S1000D review while preserving Oxygen-compatible processing-instruction annotations in the XML source.

## Maturity

**Status:** To be confirmed. Browser round-trip and Oxygen interoperability were not revalidated during the documentation reorganization.

## Features

- Render DITA and S1000D as a paginated document-oriented view.
- Highlight text and attach reviewer comments.
- Serialize Oxygen review processing instructions without rewriting unrelated XML.
- Open and save local files through browser file APIs with download/upload fallback.

## Auth

**Tier:** 1 local workflow with an app-local identity screen for annotation attribution. It is not server authentication and does not provide a security boundary.

## Port

The target default port is `8008`, followed by the next free port when needed. Current Windows, Unix, and root development defaults are not yet aligned with this target.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. No Mistral key is required for the current web-only document workflow.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:xml-proofreader` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`. The former Tauri and portable single-HTML delivery modes are not supported.

## Persistence

Business documents are opened and saved on the user's device through browser APIs. The generic backend database is not the business-document source of truth.

## LLM Configuration

The current web workflow has no LLM feature. Generic scaffold settings may still exist but are not part of the proofreading behavior.

## Tests

Use only commands declared by the backend and frontend manifests. No test or E2E command was confirmed or executed during this documentation change.

## Limitations

Browser file-system support varies by browser. Oxygen round-trip, complex XML rendering, and fallback downloads require a dedicated validation campaign.

## Standard Deviations

- The local identity screen stores client-side attribution data and is not real authentication.
- Feature UI is not fully localized.
- The frontend retains hand-written CSS and does not consistently use Tailwind or `@internal/ui`.
- Launcher defaults do not yet match the target application port.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)