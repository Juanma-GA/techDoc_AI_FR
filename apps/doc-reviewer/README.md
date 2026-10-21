# Doc Reviewer

## Purpose

Detect technical-document anomalies, review proposed changes, and export annotated PDFs for an editorial validation workflow.

## Maturity

**Status:** Functional POC. Backend checklist import, native DOCX review, and
export metadata are covered by focused tests; full conversion and browser
validation remain environment-dependent.

## Features

- Ingest PDF, DOCX, DOC, and supported ZIP inputs.
- Prepare PDFs using the native text layer where it is legible and Mistral OCR
  only for pages that need it; preparation rule results are shown per page.
- Use Airbus and English as initial mapping defaults for new imports; saved
  mapping values continue to be reused.
- Offer a no-OCR mapping suggestion from the first four pages of a PDF CMM.
  The action clears the whole draft, leaves uncertain values blank, and
  requires the user to verify and save explicitly.
- Apply deterministic technical-writing catalogs, unit checks, editable rules, and optional LLM checklist analysis.
- Accept, edit, reject, and remember review decisions.
- Review native DOCX blocks as well as PDF pages.
- Compare 2–20 text-layer PDFs against a selected reference, save comparisons
	in a separate library, review added/removed text, and export commented PDFs.
- Export original, corrected, commented, and converted outputs when the local
	converter supports them.
- Show a degradation warning before PDF/Word format conversions.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.

## CI And Repository Content

The dedicated GitHub Actions workflow is an intentional exception to the
local-first standard's CI scope. Its content-policy job rejects tracked `.pdf`,
`.doc`, and `.docx` files under `apps/doc-reviewer/`, except that a `.pdf` is
allowed when its filename contains `anonyme` (case-insensitively). It checks
file paths only and does not read document contents. This applies to committed
files, not documents imported locally while using the app.

## Demo Mode

The Settings page can enable a persistent demo mode. It loads
`frontend/public/demo/DEMO_CMM_PDF_anonyme.pdf` through the existing upload,
analysis, and review workflow; no results are simulated. The Documents tab also
offers a direct demo-PDF import action. Demo uploads and their default mapping
are stored in a separate demo scope in the same SQLite database; switching to
normal mode shows normal documents and mapping defaults unchanged.

The demo preset is `JUL 27/26`, CMM `80-80-01`, First Issue `JUL 25/95`,
revision `01`, PNR `1-900-SB`, and language `en`. Manufacturer is omitted from
the demo mapping. Demo mode uses only the isolated `demo_rules` catalog and its
demo address; normal rule activation states remain unchanged. Place the PDF at
that path locally. If a demo PDF is intentionally tracked, its filename must
contain `anonyme` to pass the content-policy check.

## Port

The target default port is `8003`, followed by the next free port when needed.
The Vite development proxy and CORS configuration use the same port.

## Prerequisites

Python 3.11+, Node 20, and pnpm 9. Mistral is optional for checklist rules. Document conversions need either Microsoft Word (desktop, Microsoft 365) or LibreOffice, chosen with `OFFICE_CONVERTER` (default: Word, then LibreOffice). With Word on a tenant with mandatory sensitivity labels, set `WORD_SENSITIVITY_LABEL_ID` (see `backend/README.md`).

## Start On Windows

Double-click `start.bat`.

## Start On Unix

Run `bash start.sh`.

## Frontend Development

```bash
pnpm --filter @apps/doc-reviewer-frontend dev
```

The Vite proxy probes the default backend port and the following ports up to
`8023`, selecting the first Doc Reviewer backend that answers `/api/v1/health`.
Set `VITE_BACKEND_PORT` when the port must be explicit. The production UI is
built with `pnpm --filter @apps/doc-reviewer-frontend build` and served by
FastAPI from `frontend/dist/`.

## Served Interface

FastAPI serves the built React/Vite application from `frontend/dist/` at `/`.

## Persistence

SQLite stores document versions, findings, review decisions, rejection memory,
saved comparison reports, and runtime configuration under `backend/data/`.
Comparison source PDFs are stored separately under
`backend/data/storage/comparisons/` and remain there until the comparison is
deleted in the Comparison tab. The optional Mistral summary receives only
changed text excerpts, not the complete PDF files.

## LLM Configuration

Mistral evaluates imported natural-language checklist rules. 
When disabled, deterministic catalogs, unit checks, and local rule paths
remain available.

## Formats And Exports

- `.pdf` uses the PDF pipeline and keeps PDF as the native working format.
- `.docx` uses the native Word pipeline with stable `dp<N>` block targets.
- `.doc` is preserved as the original and converted to DOCX for review.
- PDF, commented PDF, corrected DOCX, corrected DOC, and other converted
	outputs are listed by `GET /api/v1/documents/{id}/exports`.
- PDF-to-DOCX and Word-to-DOC conversions use Microsoft Word (or LibreOffice
	when configured) and are marked as potentially degraded in the reviewer
	before download.

## Tests

Use the backend pytest suite and frontend scripts declared in
`frontend/package.json`. Focused checklist tests pass after the rate-limit
fix. Full backend, frontend, and Playwright validation still needs to be run
on the target workstation.

## Limitations

Word conversion fidelity depends on external office software. PDF editing is constrained by fonts, layout, signatures, and source text extraction.

## Technical References

- [Detailed technical reference](../../docs/apps/doc-reviewer/technical-reference.md)
- [Backend documentation](backend/README.md)
- [Repository technical standard](../../STANDARD_POC.md)
