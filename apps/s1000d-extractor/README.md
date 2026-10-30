# S1000D Extractor

## Purpose

Transform PDF or Word source documents into an S1000D XML structure constrained by the local Issue 4.1 and 4.2 XSDs through a reusable intermediate representation and configurable target rules.

## Maturity

**Status:** Generation is constrained and checked against local Issue 4.1 and 4.2 XSDs for descriptive, procedural, and IPD data modules. Issue 5.0 remains validation-only and is not a generation target.

## Features

- Parse PDF and DOCX into a common intermediate representation.
- Classify, segment, map, and resolve S1000D element candidates.
- Accept optional DMRL, CIR, reusable user BREX profiles, and client-rule resources.
- Link generated DMs to the selected BREX DMC, guide ambiguous mappings with applicable supported rules, and validate the final XML.
- Keep title-only DMRL rows in the PMC without generating Data Modules from them.
- Flag expected Data Modules that are missing from the source before the split, with a row-level exclusion action.
- For Issue 4.1, use `S1000D_4.1_info_codes.xlsx` as the InfoCode-to-schema reference; DMRL type conflicts require an explicit user choice before splitting. If the InfoCode is missing or unmapped and the DMRL has no type, default to descriptive; unsupported schemas remain flagged for manual selection. Only descriptive, procedural, and IPD types are generated.
- Generate data-module and publication-module skeletons.
- Assign content IDs locally per DM and emit indented XML. Do not invent procedural maintenance intervals or task durations when source-backed structured values are unavailable.
- Download the PMC as `PMC-<source-name>.xml` and emit DMC components as `dmCode` attributes.
- Configure the maximum exported image dimension and choose original, JPEG, or PNG format; ZIP pictograms are kept in `pictograms/` and are not emitted as DM figures.
- Build issue/type-specific content models from the local XSDs and constrain generated elements, order, cardinality, attributes, and values.
- Collect XSD/mapping errors separately from provisional business fields that need confirmation.
- Keep XML and ZIP downloads available when generation reports XSD or mapping problems.

## Auth

**Tier:** 1 - local only, bound to `127.0.0.1`, with no authentication.


## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `llm`
- `files`
<!-- APP_PROFILES_END -->

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
the migration. Demo documents, histories, saved inputs, files and runtime
settings use a separate persistent database and storage folder. Switching back
to Normal restores the existing normal history without copying or clearing it.
BREX profiles and BREX rule uploads are unavailable in Demo mode.

## Persistence

The normal workspace remains in `backend/data/s1000d-extractor.db` and
`backend/data/storage/`. By default, the demo workspace uses
`backend/data/s1000d-extractor-demo.db` and `backend/data/storage-demo/`.
`DEMO_DATABASE_URL` and `DEMO_STORAGE_DIR` can override those demo paths. The
global mode switch is kept in the normal database; all other runtime settings
are stored with their respective workspace. Startup migrations upgrade both
databases.

## Procedural Review

The migration wizard now requires explicit type and structure confirmation. Only
procedural DMs then enter **Review the procedural DM**, before generation.
**Resume** restores the saved step without automatically advancing it.

- The entire wizard is deterministic and local, including initial DM typing.
  It does not consult the Mistral configuration or send source content to an AI
  service, even when the global LLM switch is on. Other, non-wizard features
  retain their existing LLM settings.
- PDF pages requiring OCR are rejected explicitly in the local wizard, including
  mixed text/scanned PDFs; no scanned page is silently skipped. Supply a PDF
  whose OCR was performed locally. Truly blank pages do not require OCR.
- Source roles distinguish editorial headings, chapter markers, captions,
  layout noise and table headers from requirement content. These source anchors
  remain available to the reader but do not become resource names or decisions
  to confirm. Bare numeric text is not discarded merely for looking like a
  number: technical quantities, measurements and references remain reviewable.
- Context takes precedence over isolated keywords. Requirement section headings
  scope their content; an action mentioning a tool, spare or lubricant is not
  automatically moved out of the main procedure. Warnings/cautions belonging
  to operating steps stay with those steps, rather than becoming general safety
  requirements. Unmatched content still needs an explicit decision.
  Rule explanations and original source text remain visible in the proposal panel.
  Clear suggestions show their category as awaiting confirmation; only
  ambiguous suggestions show "Decision needed". Neither label records a human
  decision automatically.
- Classify into conditions, personnel, equipment/tools, consumables, spares or
  safety; alternatively select common information, closing conditions, procedure
  body or explicit discard. Common information precedes preliminary requirements;
  closing conditions populate `closeRqmts`, independently of initial conditions.
  Resource tables preserve recognized names, part numbers, manufacturer codes,
  quantities and units; additional columns remain remarks instead of disappearing.
  Missing required resource fields remain explicitly provisional, never inferred.
  Corrected text autosaves after a short pause. Split an unedited passage at a
  character boundary to classify its parts independently; its section context
  is retained.
- The PDF reader scrolls continuously, lazily loading page images and anchors.
  It uses original page numbers, including after PDF cutting. Exact text matches
  are highlighted on the image when "Show source" is selected. The PDF reader
  never duplicates page content as extracted text, even when a page image or
  anchor fails to load. Unavailable image anchors and unknown source pages are
  explicitly flagged instead. Repeated matching text can highlight multiple
  locations and still needs human checking.
- Word uses extracted structure with approximate reading pagination, **not**
  original Word page numbers. Tables, lists and warning blocks remain
  distinguishable.
- A procedure is reviewed only after all content passages have decisions **and** the
  reviewer confirms checking the whole DM, including empty categories. No
  detection is not equivalent to a verified absence. The separate explicit skip
  action marks every procedural review as skipped and generates from the original
  extracted structure without applying review decisions.
- Decisions, corrections, split source ranges, current procedure, selected
  passage, page and scroll position persist in SQLite, not browser storage.
  Saving failures remain visible and block leaving via wizard controls.
  Unsaved work triggers the browser's unload protection; queued requests use
  keepalive on navigation, but a failed or interrupted save is never guaranteed.
  Wait for **Saved** before closing.
- Source fingerprints, analysis generations and compare-and-swap revisions
  prevent unnoticed stale reviews or concurrent-tab overwrites. An obsolete
  review must be restarted explicitly, with double-click confirmation. Going
  back without changing the source preserves decisions.
  The procedural-rule version participates in the fingerprint: reviews made
  before the source-role/context change become stale and require an explicit
  restart, without silently migrating or discarding their saved decisions.
- Human decisions, not heading heuristics, drive reviewed procedural XML in both
  individual and ZIP exports. Skipped reviews remain distinct from reviewed ones
  and preserve the original extracted structure for generation. The original
  source tree is not rewritten. BREX-guided mapping choices remain persisted.
  Incomplete/stale procedural reviews block generation and export until they are
  reviewed or explicitly skipped against the current source. Single-document
  extraction/override/XML APIs reject wizard documents rather than bypassing this
  workflow.

The new nullable `preliminary_review_json` column is introduced by
[migration 0011](backend/alembic/versions/0011_preliminary_review.py).
Existing launchers apply Alembic migrations on startup. Restart the application
after updating; no migration of an existing user database is performed by tests.
Existing generated procedural wizard documents without a review are returned to
the review step when resumed.

### Editable requirement rules

**Settings > Requirement prefill rules** lists the effective rules by requirement
category and detection type in a panel collapsed by default. The entire header,
including its title, summary and padding, toggles the panel through the accessible
**Show rules** / **Collapse rules** button. Editor fields and actions do not toggle
it. Folding preserves the editor draft; the header indicates unsaved changes
even while collapsed. Six expandable categories replace individual rule forms:
conditions, personnel, support equipment, supplies, spares and safety. Each has
French and English keyword lists, plus a separate expandable heading-list section.
Fields stack on narrower layouts, and settings panels have separate spacing.
Existing FR/EN patterns are supplied as editable literal expressions, including
legacy heading variants. Write one expression per line; blank lines are ignored.
French and English lists are independent and may contain different numbers of
synonyms: lines are not paired translations. Each active category/type needs both
languages, at most 200 characters per expression and 1000 expressions per language
across the whole configuration. Both languages are searched regardless of the
interface language. Clear both languages to remove a category/type list.
Add, edit or remove list entries, then click **Save rules**. Saving removals or
replacements, and discarding unsaved edits, require a second click within three
seconds; additions save immediately.

Keywords match complete literal expressions at word boundaries; section/column
headings match the entire normalized label. Case and accents are ignored, and
editorial numbering is removed from headings, not from technical values.
No regular expression or automatic translation is executed. Recognized S1000D
phases, operating actions, typed warnings and source-role safeguards remain
protected. Rules only propose destinations; human confirmation remains mandatory.
Conflicting expressions assigned to different categories are rejected explicitly.
Deleting every entry is supported and does not silently restore defaults.

The dedicated `GET/POST /api/v1/settings/preliminary-rules` API validates the
complete bilingual configuration and stores it in the existing `AppConfig` table
under `preliminary_rules`. No migration, new dependency or account is required.
Settings apply to this mono-user installation, survive restarts and document
resets, and do not enter browser storage. Save failures preserve the local draft;
concurrent settings saves are rejected using a compare-and-swap revision.
The API uses `{revision, groups: [{category, kind, fr: [...], en: [...]}]}`.
Previously saved paired `rules` JSON remains readable: equivalent expressions
are grouped without changing the effective matching sets. Reads and unchanged
saves do not rewrite that JSON or increment its revision; the next actual edit
stores the grouped format.
Restart the application after this update so its backend and rebuilt frontend
use the same grouped API contract.

The saved rule configuration participates in review fingerprints. Effective
changes invalidate previous reviews, including completed reviews, without
rewriting or deleting saved decisions. Resume the wizard and explicitly restart
each stale review before generation or XML/ZIP export. Saving identical rules
does not invalidate reviews. New reviews, explicit restarts and passage splits
all use the saved rules. The original source IR remains unchanged.
Reading legacy paired settings, including defaults, preserves their original
review fingerprint: regrouping expressions alone does not make reviews stale.

The implementation targets the bundled official Issue 4.1/4.2 `proced.xsd`
content models: optional common information, preliminary requirements, nested
operating steps and closing conditions. See the [official S1000D download portal](https://users.s1000d.org/Default.aspx)
for the specification and its terms. XSD validity alone is not proof of correct
technical authoring or project BREX compliance. Section recognition remains
deterministic FR/EN heuristics, not semantic understanding of arbitrary manuals.
No default `productionMaintData` block, maintenance threshold or four-hour task
duration is generated without source-backed structured input. The current review
does not provide a structured maintenance-duration editor.

Synthetic reference procedures cover all six requirement categories, source
roles, common/closing information, local warning placement, structured resources, splitting,
source offsets, omissions among extracted passages, resume, concurrent saves and
Issue 4.1/4.2 XML/ZIP consistency. These are engineering checks, **not** measured
precision/recall or review-time guarantees on real manuals. User trials still
need annotated representative procedures, agreed omission thresholds, median/
tail review time and action-count measurements. Do not copy real user documents
into test fixtures.

## LLM Configuration

Mistral supports context classification. Behavior with LLM disabled is not sufficiently documented and remains to be confirmed.

## Tests

Use synthetic fixtures with the backend pytest suite and the frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:s1000d-extractor`.

From `backend`, run `.\.venv\Scripts\python.exe -m pytest` on Windows.
From `frontend`, run `pnpm typecheck`, `pnpm test`, `pnpm lint`, `pnpm build`
and `pnpm test:e2e -- preliminary.spec.ts`.
If bundled Chromium is unavailable, an already installed Edge can run the
browser tests without downloading a browser:

```powershell
$env:E2E_PORT = '5186'
$env:E2E_BROWSER_CHANNEL = 'msedge'
pnpm test:e2e -- preliminary.spec.ts
```

Browser tests intercept every API request with synthetic responses; they do not
open a user database or existing uploads. Screenshots are written to
`frontend/test-results/`. The backend suite uses its own temporary database and
storage directory and disables real provider keys.

## Validation Note (2026-10-14)

`bash scripts/check_standard.sh` could not run in the available Windows Bash environment: CRLF line endings caused shell parsing errors before the checks started. Standard compliance remains unverified for this change.

## Procedural Review Validation (2026-10-27)

- Repository `check_standard.sh`: all 18 checks passed with the installed Git Bash.
- Frontend typecheck, lint and production build: passed; the served bundle was rebuilt.
- Vitest: 40 tests passed.
- Playwright: 4 synthetic review scenarios passed using installed Edge, covering
  scrolling and resume, save failure/retry, PDF highlighting, dark/light layouts,
  FR/EN, keyboard confirmation and explicitly reviewed empty procedures.
- Backend: 332 tests passed; the existing
  `test_large_descriptive_levelled_para_has_bounded_match_states` failed with
  60,796 pruning calls against a limit of 50,000. The same failure was reproduced
  with the serializer from `HEAD`, without changing working-tree files.
- The new Alembic migration is tested only on temporary synthetic databases;
  no existing user database was read or migrated.

The backend suite is therefore **not fully green**. External AACF compliance is
not verified. Browser checks use mocked synthetic APIs; real-manual review-time
and omission measurements remain to be performed by users.

## Limitations

Generated XML remains an incomplete working skeleton until its listed provisional business fields are confirmed. Source structures without a supported mapping are omitted from the XML and reported; IPD catalogs currently receive only the minimum XSD-compatible provisional structure when no part records are available. Generated XML never uses `TODO` as a value.

## BREX handling

The uploaded BREX is a user-supplied S1000D Data Module and is treated as the source of project rules. `brex.xsd` describes the structure of a BREX Data Module; it is not used to validate generated technical DMs. Generated DMs are checked against their descriptive, procedural, or IPD XSD and separately against the selected user's BREX rules. The app assumes the supplied BREX is correct and does not validate it against `brex.xsd`.

BREX uploads are parsed according to the XML encoding declaration and normalized to UTF-8 for storage. Recognized HTML5 named character entities are converted to numeric XML character references; unknown names are rejected. Internal DTD subsets are accepted without entity resolution; external DTDs remain blocked.

The current rule engine applies `structureObjectRule` paths, `allowedObjectFlag` values 0/1/2, closed single-value and pattern restrictions, and `contextRules` whose `rulesContext` schema URI exactly matches the generated DM's schema URI. Before serialization, BREX guidance may select an existing IR mapping candidate when that reduces BREX errors without increasing XSD errors. It never invents missing source content; unsatisfied mandatory rules remain visible. The BREX preview classifies parsed rules as directly interpretable, schema-contextual, or not automatically evaluated. Non-context, notation, and SNS rule families are shown as detected but not automatically evaluated. Unsupported value forms and unevaluable object paths are reported as unverifiable rather than treated as passing.

The completed generation view shows the selected XML BREX profile's coverage once, groups identical non-evaluation warnings across DMs, and keeps actual rule violations with their DM. A result with no violations means no violation was detected among automated and applicable rules; unsupported rules are explicitly identified as unchecked.

BREX profiles can be deleted from the migration profile selector after double-click confirmation. Deletion is blocked while any document references the profile.

## Standard Deviations

- Domain dependencies include PyMuPDF, python-docx, lxml, and openpyxl.
- Theme and language preferences may use browser storage; no authentication or business state may be stored there.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
