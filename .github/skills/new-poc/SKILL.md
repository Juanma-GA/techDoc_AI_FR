---
name: new-poc
description: "Use when: creating or scaffolding a new POC application from apps/_template, choosing its slug and port, or planning template substitutions. Do not use for: copying an existing POC, modifying an existing application, or creating files without explicit approval."
---

# New POC

## Purpose And Non-Goals

Create a standards-aligned POC from `apps/_template` with controlled, reviewable mutations. Never use another instantiated app as the source.

## Expected Inputs

- Application slug and display name.
- Business purpose and declared profiles.
- Web-only or web + optional Tauri desktop; backend stack and native target platform.
- Requested default port or permission to select the next unassigned target port.
- Explicit approval of a proposed mutation batch.

Ask for missing values and reject ambiguous or unsafe slugs.

## Normative Documents

1. Current external AACF templates and rules when accessible.
2. `STANDARD_POC.md`, especially the new-POC procedure.
3. `CLAUDE.md` for local safety and structural-change approval.
4. `docs/standards/app-readme-template.md` for application documentation.
5. `docs/apps/README.md` for target port assignments.

## Procedure

1. Validate that the slug is lowercase kebab-case, unused under `apps/`, and suitable for package and database names.
2. Confirm the business scope, profiles, display name, and unique target default port.
3. Inspect `apps/_template` and the documented creation procedure without reading prohibited data.
4. Present one mutation batch listing every path to create or modify, substitutions, expected scripts, and validations.
5. Obtain explicit approval for that exact batch.
6. Prefer `node scripts/new_poc.mjs <slug> [port] [--desktop]` (or the compatible `new_poc.sh` wrapper). Use `--dry-run` to review resolved identity and port without mutations. The default backend remains FastAPI; do not convert existing Go apps to Python.
7. Otherwise use the documented manual fallback: copy `_template`, exclude generated/data directories, replace template markers, create the matching packaging script from `scripts/package_TEMPLATE.py`, and update root workspace scripts.
8. Search the created source and configuration for unresolved `TEMPLATE`, `_template`, template logger, database, package, and port markers.
9. Validate README sections, launchers, backend tests, frontend tests, and packaging paths.
10. Report every executed and blocked validation separately.

For desktop scaffolding, copy only the canonical optional assets under
`apps/_template/desktop`, never an existing application's Tauri sources.
Validate identity, backend preparation, resource paths, health readiness and
child-process shutdown. Follow `docs/standards/desktop-and-stacks.md`.

Any change outside the approved path list requires a new mutation batch and confirmation.

## Optional Capabilities And Fallbacks

- Without shell execution, provide the exact mutation batch and manual steps; do not claim the app was created.
- Without write access, return a proposed file tree, substitutions, and validation plan.
- Without live AACF access, report `AACF NON VERIFIABLE` and apply only the local standard.
- If neither the script nor a reliable copy capability is available, stop after the plan rather than partially scaffolding.

## Validations

- Slug, package names, database name, logging namespace, and root scripts use the new identifier.
- Default port is unique in `docs/apps/README.md`; both launchers start from it and implement the same free-port behavior.
- App README follows `docs/standards/app-readme-template.md` and declares profiles and deviations.
- Required launcher, packager, backend, frontend, migration, and test files exist.
- No unresolved template markers remain outside intentional template documentation.
- Record `check_standard`, tests, build, and packaging as executed or recommended.

## Expected Output

Return an English report containing inputs, approved mutation batch, files created or modified, substitutions, validations executed, blocked or recommended validations, deviations, and next review points.

## Limits

Do not invent a new stack, add dependencies, modify shared UI or design tokens, or copy another active POC without a separately approved structural change.

## Safety

Never copy databases, `backend/data`, storage, uploads, user files, caches, built packages, secrets, or API keys. Never delete an existing application. Never mutate files before explicit batch approval.
