---
name: repository-onboarding
description: "Use when: discovering or onboarding to a POC monorepo based on this framework, its applications, authority hierarchy, documentation map, risks, or recommended reading order. Do not use for: compliance verdicts, code changes, deployment, or application creation."
---

# Repository Onboarding

## Purpose And Non-Goals

Build a factual, read-only map of the repository so a contributor can work safely. Do not issue compliance verdicts or modify files.

## Expected Inputs

- Repository root or an accessible repository snapshot.
- Optional application or documentation scope.
- Optional contributor goal.

If an input is missing, use the current repository and state the assumed scope.

## Normative Documents

Consult sources in this order:

1. Current external AACF content, when accessible, for framework authority.
2. `STANDARD_POC.md` for local technical rules.
3. `CLAUDE.md` for local safety and working method.
4. `CONTRIBUTING.md` for Git and pull request workflow.
5. `docs/index.md` for the documentation map.

Treat application README files, procedures, ADRs, and historical reports according to the roles declared in `docs/index.md`.

## Procedure

1. Identify the repository root without assuming a specific editor, shell, or hosting service.
2. Read the authority documents and note any inaccessible source.
3. Inventory directories directly under `apps/`; distinguish `_template` from instantiated applications. In a consumer monorepo with a `framework/` submodule, identify `framework/apps/_template` as the canonical template and do not expect a mirrored `apps/_template`.
4. Read `docs/apps/README.md` and compare instantiated app entries with visible application directories; check the template entry against the canonical template's actual location.
5. For each application, inspect its README, manifests, launchers, test configuration, and only the source tree names needed to identify ownership boundaries. Do not inspect implementation bodies merely to assess quality or compliance; that belongs to `audit-standard`.
6. Identify shared packages, design tokens, scripts, ADRs, skills, and harness adapters.
7. Compare documented default ports with visible launcher configuration; report differences without choosing a hidden winner.
8. Produce a recommended reading and validation path for the stated contributor goal.

## Optional Capabilities And Fallbacks

- Repository search may accelerate discovery. Without it, navigate known paths from `docs/index.md` and list unverified areas.
- Live AACF access may establish framework freshness. Without it, state `AACF NON VERIFIABLE` and continue with local orientation only.
- Command execution is not required. Suggest commands without claiming they ran.

## Validations

- Confirm every listed application exists in the inspected snapshot.
- Separate target port assignments from observed launcher defaults.
- Treat automatic fallback to the next free port as expected behavior; report only differences in default assignments or missing fallback behavior.
- Check that referenced documents exist.
- Label historical and operational documents as non-normative.
- Distinguish checks executed from checks recommended.

## Expected Output

Return an English report with:

1. Scope and limitations.
2. Authority and reading order.
3. Application inventory.
4. Repository structure and ownership boundaries.
5. Confirmed documentation or configuration risks.
6. Recommended onboarding path.
7. Proposed validations, marked as executed or recommended.

## Limits

Do not infer application maturity, compliance, or runtime health from file names. Do not write an onboarding artifact unless the user separately authorizes a mutating task.

## Safety

Never read databases, SQLite files, `backend/data`, storage directories, uploads, user-provided files, secrets, API keys, or generated personal data. Never open a file under a prohibited directory. Directory and file names may be listed only to identify an ownership boundary or required artifact.
