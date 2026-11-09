---
name: poc-validation
description: "Use when: planning, organizing, or reporting POC validation across check_standard, pytest, frontend build, typecheck, lint, Vitest, Playwright, or packaging. Do not use for: silently running commands, fixing failures, compliance verdicts, or deployment."
---

# POC Validation

## Purpose And Non-Goals

Build a risk-based validation matrix and report what was actually executed separately from what is recommended. This skill is read-only by default and does not fix failures.

## Expected Inputs

- Application slug, path, or repository-wide scope.
- Changed files or stated validation goal.
- Optional permission to execute specified checks.

If execution permission is absent, remain in planning mode.

## Normative Documents

1. `STANDARD_POC.md` defines required local checks.
2. `CLAUDE.md` defines safety and mandatory validation behavior.
3. `docs/index.md` identifies current operational documents; archived reports are not normative.
4. Application README files and manifests define app-specific commands.

## Procedure

1. Identify the changed or requested scope.
2. Discover available validation commands from manifests, application documentation, and repository scripts.
3. Build a matrix covering, when applicable: `check_standard`, backend pytest, frontend build, typecheck, lint, Vitest, Playwright smoke tests, and packaging. When shared design tokens, `framework/packages/ui/` or the canonical template (`framework/apps/_template/`) change, add `pnpm --filter @internal/design-tokens test` (theme sync + WCAG contrast), `pnpm --filter @internal/ui test`, the template `tests/e2e/design-system.spec.ts` (themes, languages, viewports, fonts loaded), and a build of every app frontend (see `docs/standards/design-system.md` §8).
4. Rank checks from narrow and cheap to broad and expensive.
5. Mark each check `required`, `recommended`, or `not applicable`, with its reason.
6. Before executing any command that may create caches, builds, reports, virtual environments, packages, or other artifacts, ask for explicit confirmation naming the commands and likely artifacts.
7. If confirmation is granted and the harness supports execution, run only the approved checks and report exact outcomes.
8. Keep pre-existing failures and blocked checks separate from regressions caused by the current change.

Never invent or translate a command across platforms. If no exact command is declared for the current environment, mark the check `command unknown`. When a required test framework is configured but no relevant tests are present, mark it `required but not implemented`, not `not applicable`.

## Optional Capabilities And Fallbacks

- Without command execution, return commands and expected evidence as `recommended`, never `passed`.
- Without a terminal, use manifest scripts and documentation to construct the matrix.
- Without a browser harness, describe Playwright or manual smoke coverage and mark it unexecuted.
- Without write permission, do not generate reports or package artifacts; return the report in the response.

## Validations

- Every reported pass or failure must correspond to an executed command or observed result.
- Every proposed command must quote its repository source or be labeled as a user-supplied command.
- Include exit status or the narrowest available result evidence.
- Distinguish blocked, skipped, recommended, and executed checks.
- Identify artifacts that an approved command may have produced.

## Expected Output

Return an English report with scope, discovered commands, a flat validation matrix, execution approvals, executed results, recommended checks, blockers, and residual risk.

## Limits

Validation does not imply AACF or local standard compliance. A failed check is reported, not repaired, unless the user starts a separate mutating task.

## Safety

Never inspect user databases, uploaded files, storage, secrets, or generated personal data. Never package user data. Never execute a command not explicitly approved when it may write artifacts.
