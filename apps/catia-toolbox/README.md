# CATIA Toolbox

## Purpose

Identify and compare CATIA delivery data, validate imported structures, and run confirmed conversions through the locally installed CATIA Composer Converter.

## Maturity

**Status:** To be confirmed. Existing pipeline claims were not revalidated during the documentation reorganization.

## Features

- Identify parts from nomenclature and delivery inputs.
- Filter optimized parts using the `X000` marker in the nomenclature.
- Compare 2 to 10 nomenclature versions by SIN, either chronologically or against a selected reference.
- Compare imports and verify naming, depth, duplication, and structure rules.
- Prepare CATPart-to-Composer conversion plans and execute selected conversions through `ComposerConverter.exe`.
- Optimize a Composer parts folder by copying only `.smgXml` and `.smgGeom` files
  to a new `<folder>_optimized` subfolder; unrelated source entries are ignored
  and the selected source files remain unchanged.
- Rename SMGXML references and prepare part replacement plans.
- Colorize mono-body SMGXML pieces in the work folder created by optimization,
  matching profile references from the nomenclature's Materials slots by OLD P/N.
  Dry-run is the default; confirmed writes update that folder without backups.
- Use the native file/folder picker when no Source root is configured; selected
	files are copied into the local application storage before processing.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Port

The target default port is `8004`, followed by the next free port when needed. The current Unix launcher uses a different default.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. Real conversion requires CATIA Composer Converter and an XML conversion profile saved from Composer Converter. CATIA, OneDrive, UNC shares, or local folders apply only to relevant workflows.

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

From the repository root, run `pnpm dev:catia-toolbox` after confirming its configured backend port.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores imports, nomenclature analyses, workflow results, and runtime configuration under `backend/data/`. Legacy colorization and plan history is retained; the new tree cleanup does not store run history.
Native local selections are staged below `backend/data/storage/local/` and remain
confined to that storage root for subsequent reads.

## LLM Configuration

Mistral credentials can still be configured and tested in Settings; active workflows do not require an LLM.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`.
The frontend `test` script excludes Playwright files; use `test:e2e` for browser
scenarios.

## Limitations

CATIA Toolbox auto-detects `ComposerConverter.exe` under the standard Dassault Systemes installation folder. A custom executable path and the required XML conversion profile can be configured on the Conversion screen. Real conversion requires a two-click confirmation, never modifies source CAD files, and reports a failure unless Composer creates or updates an expected `.smgXml` or `.smg` output.

## Standard Deviations

- Metadata-only folder scanning may read directory structure outside `backend/data/storage/` because it is a core local workflow.
- Some UI styling remains app-specific instead of using only shared primitives.
- Windows and Unix launcher defaults are not yet aligned.

## Technical References

- [Detailed technical reference](../../docs/apps/catia-toolbox/technical-reference.md)
- [Repository technical standard](../../STANDARD_POC.md)
