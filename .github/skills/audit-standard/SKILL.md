---
name: audit-standard
description: "Use when: auditing one POC against the repository-local STANDARD_POC.md, checking local standard compliance, or producing the PROMPT_AUDIT_STANDARD.md report. Do not use for: AACF compliance verdicts, automatic fixes, code changes, or whole-repository onboarding."
---

# Audit Standard

## Purpose And Non-Goals

Perform a factual, read-only audit of one `apps/<poc>` application against the local repository standard. This skill is the core local compliance workflow. It does not replace external AACF compliance and never applies corrections.

## Expected Inputs

- Application slug or unambiguous application path.
- Repository root or accessible snapshot.
- Optional audit scope; default is the full local standard.

Ask for clarification when the application or scope is ambiguous.

## Normative Documents

1. Current external AACF content has priority when accessible, but AACF findings remain separate.
2. `STANDARD_POC.md` is the normative source for the local audit.
3. `PROMPT_AUDIT_STANDARD.md` is the required checklist and report format.
4. `CLAUDE.md` supplies local safety and method constraints.
5. Accepted ADRs and documented app deviations apply only within their stated scope.

Never use `STANDARD_POC.md`, `CLAUDE.md`, or a local script as proof of AACF compliance.

## Procedure

1. Verify that the requested application and local normative documents are accessible.
2. Determine declared application profiles and documented deviations from its README.
3. Follow every applicable checklist domain in `PROMPT_AUDIT_STANDARD.md`.
4. Inspect source, configuration, schemas, migrations, manifests, launchers, tests, and documentation only as needed for evidence.
5. Record file and line evidence when the harness exposes line positions. Otherwise provide the narrowest available path and quote.
6. Classify every item as compliant, partial, non-compliant, not applicable, or unverified.
7. Separate observed repository state from commands or runtime behavior not executed.
8. Produce the report structure required by `PROMPT_AUDIT_STANDARD.md`, followed by a severity-ordered remediation plan.

Do not issue a `COMPLIANT` local verdict while any applicable checklist item is partial or unverified. Never infer implementation details from dependencies, file names, neighboring apps, or standard conventions.

## Optional Capabilities And Fallbacks

- Without repository search, inspect the paths enumerated in `PROMPT_AUDIT_STANDARD.md` and mark uncovered patterns unverified.
- Without command execution, do not run `scripts/check_standard.sh`, tests, builds, or packaging; list them as recommended.
- Without line metadata, cite file paths and exact evidence snippets.
- Without live AACF access, state `AACF NON VERIFIABLE`; the local verdict may still be issued.

## Validations

- Cover each applicable checklist domain from `PROMPT_AUDIT_STANDARD.md`.
- Confirm that each finding has evidence, impact, and a concrete proposed action.
- Downgrade the verdict when evidence is partial or an applicable control is unverified.
- Verify that no correction was applied.
- Keep the AACF status separate from the local verdict.
- List controls that could not be assessed and why.

## Expected Output

Return the audit report in English using the section order and tables defined by `PROMPT_AUDIT_STANDARD.md`. Include the local standard version or commit when available, the declared auth tier, the local verdict, detailed findings, unverified controls, and a severity-ordered remediation plan.

## Limits

This skill audits one application. Use a separate orchestration wrapper for a whole-repository control. Findings are proposals only and require a distinct mutating task to fix.

## Safety

Never inspect databases, SQLite files, `backend/data`, storage, uploads, user files, secrets, API keys, or generated personal data. Never edit, delete, rename, reset, commit, install, deploy, or migrate.
