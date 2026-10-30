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
  only for pages that need it; final verification runs enabled THALES rules on
  modified pages and uses validated OCR boxes to position scan findings.
- Configure recognized THALES preparation titles in Rules > Page titles.
  Pages without a new recognized title continue the previous section; titles
  outside the list are ignored. Rerun detection to apply catalog changes to
  prepared documents.
- Use Airbus and English as initial mapping defaults for new imports; saved
  mapping values continue to be reused.
- Offer a no-OCR mapping suggestion from the first four pages of a PDF CMM.
  The action clears the whole draft, leaves uncertain values blank, and
  requires the user to verify and save explicitly.
- Apply deterministic technical-writing catalogs, unit checks, editable rules, and optional LLM checklist analysis.
- Accept, edit, reject, and remember review decisions.
- Review native DOCX blocks as well as PDF pages.
- Compare 2–20 text-layer PDFs against a selected reference in a synchronized
	side-by-side viewer. Page text is aligned in reading order at 85% similarity
	or above; missing or
	changed page runs are signalled, and linked difference boxes reveal removed
	and added text only on paired pages. The viewer navigates only paired pages and
	shows both page numbers (e.g. reference p. 7 alongside revision p. 9).
	Unmatched page numbers are listed, but their pages are not shown or text/box
	analyzed. Saved comparisons remain in a separate library and export as
	commented PDFs.
- Export original, corrected, commented, and converted outputs when the local
	converter supports them.
- Show a degradation warning before PDF/Word format conversions.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

## Repository Content Policy

Before committing files, keep `apps/doc-reviewer/` free of `.doc` and `.docx`
files. A committed `.pdf` is allowed only when its filename contains `anonyme`
(case-insensitively). This policy concerns file paths only; it does not inspect
document contents or restrict documents imported locally while using the app.

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

In demo mode, Comparison offers **Load both demo PDFs**. This replaces the draft
selection with the original and `DEMO_CMM_PDF_revision_anonyme.pdf`, selects the
original as reference, and leaves **Compare and save** as an explicit action.
Both PDFs retain the same two pages, embedded fonts, layout, and text order.
The revision contains exactly four localized text changes:

| PDF page | Original | Demo revision |
| --- | --- | --- |
| 1 | `REVISION No. 01 DATED JUL 27/26` | `REVISION No. 02 DATED JUL 27/26` |
| 1 | `New presentation and new date.` | `New presentation and new data.` |
| 1 | `Page 701 to 704` | `Page 701 to 702` |
| 2 | `1-900-SB` | `1-901-SB` |

These are synthetic comparison examples, not operational maintenance changes.
The real comparison engine detects four removed lines and four added lines,
with both pages paired. Loading is atomic: a missing/invalid asset reports an
error without replacing the existing selection. The button is absent in normal
mode. Comparisons continue to use their existing saved-comparison library;
unlike document uploads, that library is not separated into normal/demo scopes.

Comparison downloads remain native links and use the shared secondary button
variant at its normal size with a download icon. They are excluded from the
app's generic link-color rule so text contrast stays readable in both themes.

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
changed text excerpts from paired pages and page numbers for unmatched pages;
unmatched page content is not included. It does not receive the complete PDF
files.
Older saved reports are reprocessed from their locally stored source PDFs the
first time they are opened in the visual comparison viewer.

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
