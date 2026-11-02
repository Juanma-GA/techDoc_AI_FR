# CATIA Toolbox

## Purpose

Identify and compare CATIA delivery data, prepare Composer assets, and run confirmed conversions through the locally installed CATIA Composer Converter. All workflows are deterministic and run locally.

## Maturity

**Status:** To be confirmed. Existing pipeline claims were not revalidated during the documentation reorganization.

## Features

- Identify parts from nomenclature and delivery inputs.
- Nomenclature and Materials previews and analyses are started explicitly.
  Selecting another file clears the previous preview, column mapping, and active
  result; the new mapping is detected from that file, not reused from another one.
  Imported files remain distinct by their full storage path, even with the same
  filename. A late analysis response is saved without changing the selected file.
- Filter optimized parts using the `X000` marker in the nomenclature.
- Compare 2 to 10 nomenclature versions by SIN, either chronologically or against a selected reference.
- Compare imported folder structures.
- Screen old and new CATPart folders using GE identifiers. Files with the same SIN and PN are shown as identical; GE files with a shared SIN but different PNs remain reviewable. The Excel workbook includes separate Solo A and Solo B sheets for GE SINs absent from the other folder.
- Prepare CATPart-to-Composer conversion plans and execute selected conversions through `ComposerConverter.exe`.
- Optimize a Composer parts folder by copying only `.smgXml` and `.smgGeom` files
  to a new `<folder>_optimized` subfolder; unrelated source entries are ignored
  and the selected source files remain unchanged.
- Rename SMGXML references from a nomenclature or an explicit mapping.
- Colorize mono-body SMGXML pieces in the work folder created by optimization,
  matching profile references from the nomenclature's Materials slots by OLD P/N.
  Dry-run is the default; confirmed writes update that folder without backups.
- Use the native file/folder picker when no Source root is configured; selected
	files are copied into the local application storage before processing.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `files`
<!-- APP_PROFILES_END -->

## Port

The target default port is `8004`, followed by the next free port when needed. The current Unix launcher uses a different default.

## Prerequisites

Python 3.11+, Node 24.22.1 or later within Node 24, and pnpm 12.15+. Real conversion requires CATIA Composer Converter and an XML conversion profile saved from Composer Converter. The CATPart screening workflow reads filename metadata only, supports up to 20,000 files per folder, and does not require CADMPEG or CATIA V5. CATIA, OneDrive, UNC shares, or local folders apply only to relevant workflows.

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

## Configuration

Settings contains the input/output roots, Composer license server, converter executable, and XML conversion profile. Saving updates all fields together. These settings are kept when clearing application data.

Historical Alembic migrations and existing database tables are preserved. Removed modules are no longer registered in the API, ORM, navigation, or administration counters; no destructive migration is run against existing data. The replaced-part columns used by nomenclature analysis and SMGXML renaming remain available.

## Interface

The four workflow groups cover identification, preparation, processing, and integration. Data management and settings are available under Tools. Desktop uses the shared sidebar; screens up to 760 px use a compact navigation select. Container queries adapt the content to the actual workspace width, including a collapsed desktop sidebar. Large tables scroll inside their own region, and long filenames wrap rather than widen the page.

Routes load on demand, leaving the shared shell and navigation available while an individual screen is loading.

Controls use `@internal/ui` and shared design tokens. App-local styles only define business layouts, tables, lists, and feedback. Page sections, feedback, metrics, and file browsers remain unframed, without decorative borders or colored accent bars. Functional borders are kept on controls and tables. Comparison tabs support arrow keys, Home, and End. Destructive actions still require a second click within three seconds.

## Shared UI Follow-ups

No shared package or template was modified. The following improvements belong upstream:

- `AppShell`: mobile rules in `app-shell.css` are overridden by the later sidebar stylesheet, leaving a desktop-width sidebar and vertical navigation on small screens. This app uses the existing `--sidebar-w` customization variable at the mobile breakpoint; the cascade should be fixed centrally.
- `AppShell` / template: offer a compact mobile-navigation slot or reuse the app's select pattern instead of giving grouped navigation a separately scrollable area above the workspace.
- `AppShell`: reserve enough header space for the application title beside the collapse and theme controls; the default desktop width currently truncates even this application's title.
- `Select`: `appearance-none` removes the native indicator without providing a replacement. Add a visible Lucide dropdown indicator in the shared component.
- Template: pass translated loading labels to `Spinner`; its current default accessibility label is French even when the application is English.

## Tests

Use the backend pytest suite and frontend scripts declared in `frontend/package.json`.
The frontend `test` script excludes Playwright files; use `test:e2e` for browser scenarios. Playwright uses port 5188 and synthetic API responses, never the user's database or uploads. The suite covers all active pages at 360, 768, 1280, and 1920 px, mobile navigation, retired-route redirects, local settings, keyboard tabs, theme/language controls, double-click reset confirmation, CATPart screening/export, and same-named nomenclature imports with delayed preview/analysis responses.

## Limitations

CATIA Toolbox auto-detects `ComposerConverter.exe` under the standard Dassault Systemes installation folder. A custom executable path and the required XML conversion profile can be configured on the Conversion screen. Real conversion requires a two-click confirmation, never modifies source CAD files, and reports a failure unless Composer creates or updates an expected `.smgXml` or `.smg` output.

## Standard Deviations

- Metadata-only folder scanning may read directory structure outside `backend/data/storage/` because it is a core local workflow.
- Business tables, file-browser layouts, workflow sections, and metrics remain app-specific because the shared package has no matching business components. Primitive controls and their appearance come from `@internal/ui`.
- Windows and Unix launcher defaults are not yet aligned.

## Technical References

- [Detailed technical reference](../../docs/apps/catia-toolbox/technical-reference.md)
- [Repository technical standard](../../STANDARD_POC.md)
