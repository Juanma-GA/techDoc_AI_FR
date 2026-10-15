# Image Replace

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## Profiles

- `local-first`: image processing and persistence are local.
- No `llm` profile: PaddleOCR and LaMa run locally; no remote LLM or AI API is used.

## Purpose

Find text references in technical images and replace selected references with supplied values. Users can enter pairs manually or load them from an Excel workbook.

## Maturity

**Status:** Local POC workflow integrated. API and UI behavior are covered by synthetic tests; actual PaddleOCR and LaMa model inference has not been run as part of this integration.

## Features

- Upload PNG, JPEG, WEBP, BMP, or TIFF images up to 15 MB.
- Optionally upload `.xlsx` / `.xlsm` workbooks up to 15 MB, select the sheet, map reference/replacement/ICN/part columns, and select the part section. The selected part's pairs are previewed and can be edited or removed before OCR.
- Add manual replacement pairs; these are combined with the edited Excel pairs.
- Run PaddleOCR on CPU, inspect recognized text and matches, and download the replacement image as a 2480 × 3508 px A4 JPEG at 300 dpi.
- Zoom and pan the result, then paint a mask to remove an area with local LaMa inpainting or local median-color fill.
- No image, workbook, or generated result is persisted by the application.

## Port

The main API and React UI use default port `8010`; the internal LaMa service uses `8011`. Launchers select another free port if a default is busy and pass the selected local LaMa port to the API. See the [application inventory](../../docs/apps/README.md).

## Prerequisites

- Python 3.13 for the PaddleOCR API and Python 3.11 for the LaMa service.
- Node 20 and pnpm 9 for frontend development and builds.
- Windows: `py` launcher and `curl.exe`. The launcher can install Python 3.11 from the repository installer; Python 3.13 must already be installed unless using a package with embedded runtimes.
- Unix: `python3.13`, `python3.11`, `lsof`, and `curl`.
- Package users do not need a system Python; the Windows package includes separate Python 3.13 and 3.11 runtimes.

Dependencies install on first launch. PaddleOCR model files may download on first OCR, and LaMa model files may download on first inpainting. After setup, model inference runs locally on CPU.

## Start On Windows

Double-click `start.bat`. It starts the API and LaMa service in local console windows, builds the React UI if absent or stale, and opens `http://127.0.0.1:8010/` (or the selected API port).

## Start On Unix

Run `bash start.sh`. The launcher starts the LaMa service alongside the API and stops its child process when the launcher exits. The app opens at `http://127.0.0.1:8010/` unless another free port is selected.

## Frontend Development

Run `start.bat` once to create and install the two Python environments. Stop its API window; the already-running LaMa service may be reused. From the repository root, run:

```bash
pnpm dev:image-replace
```

The command starts the API, LaMa (or reuses its local health endpoint), and Vite. Vite proxies `/api` to the API on port `8010`.

## Served Interface

FastAPI serves the built React application from `frontend/dist/` at `/`. If the bundle is absent, `/` returns HTTP 503 with build instructions; there is no standalone preview UI.

## Persistence

The app uses the gitignored SQLite database `backend/data/image-replace.db` for the standard application configuration. Uploaded images, workbooks, OCR output, and retouched images are processed in memory or temporary files and are not persisted by the application.

## LLM Configuration

Not applicable. No remote LLM is used. PaddleOCR and LaMa are local model workflows.

## API

- `GET /api/v1/health`
- `POST /api/v1/image-replace/excel/sheets`
- `POST /api/v1/image-replace/excel/columns`
- `POST /api/v1/image-replace/excel/pieces`
- `POST /api/v1/image-replace/excel/pairs`
- `POST /api/v1/image-replace/ocr`
- `POST /api/v1/image-replace/inpaint`

The LaMa service is internal to the local application and listens on `127.0.0.1:8011` by default.

## Tests

### Executed during integration

- Backend: 19 pytest tests passed, including synthetic image/Excel cases, OCR API tests with a mocked engine, and LaMa proxy/service validation.
- Backend and helper scripts: Ruff passed for the changed feature modules and packaging/dev helpers.
- Frontend: TypeScript check, ESLint, 5 Vitest tests, and production build passed.
- Browser smoke: 2 Playwright tests passed with synthetic files and mocked API responses on an isolated Vite port.
- Repository: all 16 `check_standard.sh` checks passed using a temporary LF-normalized copy because the checked-in shell script has CRLF line endings.
- Packaging: Python compilation and `python -X utf8 scripts/package_image-replace.py --help` passed. No ZIP was created.

## Performance diagnostics

The API console emits structured `image_ocr_timing` and `image_inpaint_timing` events with stage durations and image/crop dimensions only; they do not include image contents, filenames, or detected text. Run one OCR and one LaMa operation, then share those log lines. LaMa inference uses a 256 px context margin around the painted mask and merges the result only into masked pixels.

To compare PP-OCRv6 sizes, set `OCR_MODEL_VARIANT=small` or `OCR_MODEL_VARIANT=tiny` in `backend/.env` and restart the API; the default is `medium`. Each selection changes only the detection/recognition model pair.

To benchmark CPU thread counts, set `OCR_CPU_THREADS` in `backend/.env` and restart the API; the default is 10. The OCR timing event includes the active model variant and thread count.

### Recommended for real-model validation

- Run OCR with a synthetic image after the first model download.
- Run LaMa inpainting with a synthetic image and mask after the first model download.
- Inspect image/Excel workflows in both themes and at desktop and narrow-screen widths.

## Limitations

- The launcher requires compatible Python runtimes on developer machines; package users receive embedded runtimes.
- The first dependency/model setup requires network access. Subsequent inference is local.
- Model accuracy, latency, and packaging size have not been benchmarked with representative production images.
- The backend preserves the source OCR and Excel behavior; frontend labels and error messages are localized, while some backend validation details remain French.

## Standard Deviations

### Single workflow tab

- **Rule:** `STANDARD_POC.md` §4 describes Home, Data, and Settings tabs.
- **Deviation:** The app exposes one workflow tab, Detection, plus Settings; the Data UI route is not registered.
- **Reason:** Image detection and replacement is the sole business workflow for this POC.
- **Approval:** Explicitly approved by the product owner for this app.
- **Review condition:** Revisit if the product adds a separate data-management workflow or the standard changes.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application README template](../../docs/standards/app-readme-template.md)
- [Application inventory](../../docs/apps/README.md)
- [Canonical template](../_template/)
