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
the migration.

## Persistence

SQLite stores projects, source metadata, intermediate structures, mappings, outputs, findings, and runtime configuration under `backend/data/`.

## LLM Configuration

Mistral supports context classification. Behavior with LLM disabled is not sufficiently documented and remains to be confirmed.

## Tests

Use synthetic fixtures with the backend pytest suite and the frontend scripts declared in `frontend/package.json`. The repository declares `test:e2e:s1000d-extractor`.

## Validation Note (2026-10-14)

`bash scripts/check_standard.sh` could not run in the available Windows Bash environment: CRLF line endings caused shell parsing errors before the checks started. Standard compliance remains unverified for this change.

## Limitations

Generated XML remains an incomplete working skeleton until its listed provisional business fields are confirmed. Source structures without a supported mapping are omitted from the XML and reported; IPD catalogs currently receive only the minimum XSD-compatible provisional structure when no part records are available. Generated XML never uses `TODO` as a value.

## BREX handling

The uploaded BREX is a user-supplied S1000D Data Module and is treated as the source of project rules. `brex.xsd` describes the structure of a BREX Data Module; it is not used to validate generated technical DMs. Generated DMs are checked against their descriptive, procedural, or IPD XSD and separately against the selected user's BREX rules. The app assumes the supplied BREX is correct and does not validate it against `brex.xsd`.

BREX uploads are parsed according to the XML encoding declaration and normalized to UTF-8 for storage. Recognized HTML5 named character entities are converted to numeric XML character references; unknown names are rejected. Internal DTD subsets are accepted without entity resolution; external DTDs remain blocked.

The current rule engine applies `structureObjectRule` paths, `allowedObjectFlag` values 0/1/2, closed single-value and pattern restrictions, and `contextRules` whose `rulesContext` schema URI exactly matches the generated DM's schema URI. Before serialization, BREX guidance may select an existing IR mapping candidate when that reduces BREX errors without increasing XSD errors. It never invents missing source content; unsatisfied mandatory rules remain visible. The BREX preview classifies parsed rules as directly interpretable, schema-contextual, or not automatically evaluated. Non-context, notation, and SNS rule families are shown as detected but not automatically evaluated. Unsupported value forms and unevaluable object paths are reported as unverifiable rather than treated as passing.

The completed generation view shows the selected XML BREX profile's coverage once, groups identical non-evaluation warnings across DMs, and keeps actual rule violations with their DM. A result with no violations means no violation was detected among automated and applicable rules; unsupported rules are explicitly identified as unchecked.

## Standard Deviations

- Domain dependencies include PyMuPDF, python-docx, lxml, and openpyxl.
- Theme and language preferences may use browser storage; no authentication or business state may be stored there.

## Technical References

- [Repository technical standard](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
