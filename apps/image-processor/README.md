# Image Processor

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Profiles

- `local-first`: image processing and persistence are local.
- `files`: uploaded workbooks and image versions are validated, SHA-256 checked, and stored locally.
- No `llm` profile: PaddleOCR and LaMa run locally; no remote LLM or AI API is used.

## Purpose

Find text references in technical images and replace selected references with supplied values. Users can enter pairs manually or load them from an Excel workbook.

## Maturity

**Status:** Local POC workflow integrated. API and UI behavior are covered by synthetic tests; actual PaddleOCR and LaMa model inference has not been run as part of this integration.

## Features

- Upload PNG, JPEG, WEBP, BMP, or TIFF images up to 15 MB.
- Optionally upload `.xlsx` / `.xlsm` workbooks up to 15 MB, select the sheet, map reference/replacement/ICN/part columns, and select the part section. The selected part's pairs are previewed and can be edited or removed before OCR.
- Add manual replacement pairs; these are combined with the edited Excel pairs.
- Check or uncheck individual manual/Excel pairs to apply only selected references.
- Standardize replacement font size from visible character heights and the mean
  of the most common group among selected references; only shrink over-wide replacements.
- Preserve detected reading orientation, snapping angles within 5 degrees of an axis.
  The common A4 font size survives reruns, brushes, undo, and history restoration.
  See [replacement typography](./backend/README.md#replacement-typography).
- Run PaddleOCR on CPU, inspect recognized text and matches, and download the replacement image as a 2480 × 3508 px A4 JPEG at 300 dpi.
- Zoom and pan the result, then paint a mask to remove an area with local LaMa inpainting or local median-color fill.
- Every successful replacement or brush edit becomes the source for the next operation. Undo restores the previous image and analysis, one operation at a time.
- On startup, restore the last Excel workbook, sheet, and column mapping, but leave the image and selected part empty.
- History lists each image and restores its complete last workspace: source/current images, undo stack, Excel workbook, selected part, edited/selected pairs, OCR output, and operation log.
- The selected Excel ICN names the image in History and its download: `<ICN>.jpg`,
  without retouch/replacement suffixes. Downloads are real A4/300 dpi JPEGs after
  either brush mode, including before the first OCR. Downloads never alter working
  or undo revisions; print-ready JPEGs are not re-encoded.

## Port

The main API and React UI use default port `8010`; the internal LaMa service uses `8011`. Launchers select another free port if a default is busy and pass the selected local LaMa port to the API. See the [application inventory](../../docs/apps/README.md).

## Prerequisites

- Python 3.13 for the PaddleOCR API and Python 3.11 for the LaMa service.
- Node 20 and pnpm 9 for frontend development and builds.
- Windows: `py` launcher and `curl.exe`. The launcher can install Python 3.11 from the repository installer; Python 3.13 must already be installed unless using a package with embedded runtimes.
- Unix: `python3.13`, `python3.11`, `lsof`, and `curl`.
- ZIP package users do not need a system Python; the Windows ZIP includes separate Python 3.13 and 3.11 runtimes.

Dependencies install on first launch. The Windows launcher installs build tools in its embedded Python runtimes before installing app dependencies. In the web launchers and ZIP package, PaddleOCR model files may download on first OCR, and LaMa model files may download on first inpainting. After setup, model inference runs locally on CPU.

Text-line orientation uses `PP-LCNet_x1_0_textline_ori` (approximately 6.5 MB of
model weights). Web and ZIP launches may download this model on first OCR.
No images are sent to a remote service; the classifier runs locally. Its actual
CPU cost depends on all detected text lines, not just the selected replacements.

## Start On Windows

Double-click `start.bat`. It starts the API and LaMa service in local console windows, builds the React UI if absent or stale, and opens `http://127.0.0.1:8010/` (or the selected API port).

## Start On Unix

Run `bash start.sh`. The launcher starts the LaMa service alongside the API and stops its child process when the launcher exits. The app opens at `http://127.0.0.1:8010/` unless another free port is selected.

## Frontend Development

Run `start.bat` once to create and install the two Python environments. Stop its API window; the already-running LaMa service may be reused. From the repository root, run:

```bash
pnpm dev:image-processor
```

The command starts the API, LaMa (or reuses its local health endpoint), and Vite. Vite proxies `/api` to the API on port `8010`.

## Desktop (Windows x64)

The optional Tauri desktop app starts and supervises the local API and LaMa
services. It uses the same React interface and keeps its database and storage in
Tauri's app-specific local-data directory, separate from the web launcher's data.
The native window title bar follows the persisted dark/light theme and the
sidebar theme toggle.
Its startup screen remains visible while migrations run and the OCR and LaMa
models load; desktop startup is therefore longer than web/ZIP startup.

For development, run `pnpm desktop:dev:image-processor` from the repository root.
The first run creates the Python 3.13 and 3.11 development environments and
installs their dependencies. On a fresh checkout, run `pnpm install` at the
repository root first to install the Tauri CLI and frontend dependencies.

The NSIS installer is built with `pnpm desktop:build:image-processor` or
`package.bat desktop`. It bundles the React UI, backend sources, PaddleOCR tiny
detection/recognition and text-line orientation models, and the LaMa checkpoint.
During setup, it visibly downloads the embedded Python runtimes and installs
their locked dependencies from PyPI. The installer needs an Internet connection
for this step; after setup, the app runs locally and offline without system
Python or Node. NSIS silently installs WebView2 from its embedded offline
installer. The first build, or a dependency/model cache refresh, needs a trusted
network connection to prepare runtimes and models. Later builds reuse the local
cache under `dist/.cache/desktop`. Building also requires Rust and Visual Studio
C++ build tools.

## Served Interface

FastAPI serves the built React application from `frontend/dist/` at `/`. If the bundle is absent, `/` returns HTTP 503 with build instructions; there is no standalone preview UI.

## Persistence

SQLite (`backend/data/image-replace.db`) stores configuration, startup Excel selections,
history snapshots, and file metadata. File bytes are stored separately under
`backend/data/storage/{workspace_uuid}/{file_version_uuid}_{name}` with SHA-256
integrity checks. Identical versions within a workspace are reused. All this data is
local and gitignored; business state is never stored in browser storage.

Two independent persistence scopes are used:

- **Fresh home on startup:** last workbook, sheet, reference/replacement/ICN/part columns,
  and their available options. No image, selected part, or part-specific pairs are restored.
  Choose an image and then a part. **New image** also clears the selected part.
- **History:** one workspace per uploaded image, autosaved with all completed image
  operations, the full analysis, selections, and edited pairs. **Resume** does not rerun
  OCR. **Undo** also works after reopening a saved workspace. A failed OCR or brush
  operation leaves the previous image intact.

Wait for the local-save status before closing or reloading. A save failure is displayed
with a retry action; the unsaved workspace remains in memory. Missing or altered saved
files produce explicit errors rather than an empty replacement workspace.

History is retained until deleted with a two-click confirmation. Removing a workbook
from home removes the startup preset only; histories keep their own workbook versions.
Deleting a history removes its associated files without removing the startup preset.
Admin reset-all removes histories, the startup preset, and their files, but preserves
application settings. Back up the database and storage directory together; neither
is included in distributable packages.

Migration `0002_workspaces` adds the three persistence tables. Normal launchers apply it
with Alembic; do not delete or recreate the existing database to upgrade.

## LLM Configuration

Not applicable. No remote LLM is used. PaddleOCR and LaMa are local model workflows.

## API

- `GET /api/v1/health`
- `POST /api/v1/image-processor/excel/sheets`
- `POST /api/v1/image-processor/excel/columns`
- `POST /api/v1/image-processor/excel/pieces`
- `POST /api/v1/image-processor/excel/pairs`
- `POST /api/v1/image-processor/ocr`
- `POST /api/v1/image-processor/inpaint`
- `POST /api/v1/image-processor/export` (ICN-named A4/300 dpi JPEG)
- `GET /api/v1/image-processor/workspace/excel`
- `PUT /api/v1/image-processor/workspace/excel`
- `GET /api/v1/image-processor/history` (cursor-paginated, without image payloads)
- `GET /api/v1/image-processor/history/{uuid}`
- `PUT /api/v1/image-processor/history/{uuid}`
- `DELETE /api/v1/image-processor/history/{uuid}`
- `GET /api/v1/admin/stats`
- `POST /api/v1/admin/reset/history`
- `POST /api/v1/admin/reset/all`

The LaMa service is internal to the local application and listens on `127.0.0.1:8011` by default.

## Tests

### Executed for resumable editing, history, ICN downloads, and typography

- Backend: 133 pytest tests passed, including measured glyph heights, dominant font sizes,
  rendered rotations/centering, width exceptions, real JPEG/ICN exports, old-history naming,
  unchanged print-ready JPEG bytes, isolated Excel/history round trips,
  file integrity checks, disk/commit failure rollback, admin resets, and an Alembic
  upgrade/check/downgrade cycle against a temporary synthetic SQLite database.
- Backend feature modules and tests: Ruff passed. The changed validation-error
  handler passed E/F/I/W checks; its unrelated pre-existing RUF034 remains unchanged.
- Frontend: TypeScript, ESLint, 27 Vitest tests, and the production build passed.
- Browser: 7 Playwright tests passed with synthetic files and all API calls intercepted
  on isolated port `5187`, including selective OCR, both brush modes, undo, full-history
  restoration, common font-size reuse, exact ICN download names and JPEG signatures, failed exports,
  startup exclusions, keyboard use, FR/EN, dark/light, and 390 px width.
- User databases and uploaded documents were not used. Repository-wide standard
  checks, packaging, PostgreSQL migration checks, and real-model inference were not
  rerun for this change. No ZIP was created.

## Performance diagnostics

The API console emits structured `image_ocr_timing` and `image_inpaint_timing` events with stage durations and image/crop dimensions only; they do not include image contents, filenames, or detected text. Run one OCR and one LaMa operation, then share those log lines. LaMa inference uses a 256 px context margin around the painted mask and merges the result only into masked pixels.

To compare PP-OCRv6 sizes in web or ZIP mode, set `OCR_MODEL_VARIANT=small` or
`OCR_MODEL_VARIANT=medium` in `backend/.env` and restart the API. The default is
`tiny`; each selection changes only the detection/recognition model pair. The
Tauri installer always bundles the tiny variant.

To benchmark CPU thread counts, set `OCR_CPU_THREADS` in `backend/.env` and restart the API; the default is 10. The OCR timing event includes the active model variant and thread count.

The `ocr_orientation_ms` field measures the local text-line classifier separately.
Model loading/download is included in `ocr_engine_access_ms`, not in this field.
No real-model orientation benchmark was run for the typography change.

### Recommended for real-model validation

- Run OCR with a synthetic image after the first model download.
- Run LaMa inpainting with a synthetic image and mask after the first model download.
- Inspect image/Excel workflows in both themes and at desktop and narrow-screen widths.

## Limitations

- The launcher requires compatible Python runtimes on developer machines; package users receive embedded runtimes.
- The web launcher and ZIP package need network access for first-time dependency
  setup and uncached models. The Tauri setup downloads dependencies and bundles
  its models; setup needs Internet, but the installed app runs offline.
- Model accuracy, latency, and packaging size have not been benchmarked with representative production images.
- The backend preserves the source OCR and Excel behavior; frontend labels and error messages are localized, while some backend validation details remain French.

## Standard Deviations

### Business-workflow navigation

- **Rule:** `STANDARD_POC.md` §4 describes Home, Data, and Settings tabs.
- **Deviation:** The app exposes Detection, History, and Settings; the generic Data UI route is not registered.
- **Reason:** History provides the business-specific restoration and deletion workflow instead of the generic Data screen.
- **Approval:** The original navigation exception and the addition of History were explicitly approved by the product owner.
- **Review condition:** Revisit if the product adds a separate data-management workflow or the standard changes.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application README template](../../docs/standards/app-readme-template.md)
- [Application inventory](../../docs/apps/README.md)
- [Canonical template](../_template/)
