---
name: git-pr-workflow
description: "Use when: planning or performing the repository branch, commit, rebase, push, or pull request workflow for one task. Do not use for: destructive history rewrites, direct main work without explicit approval, or combining unrelated tasks."
---

# Git And Pull Request Workflow

## Purpose And Non-Goals

Keep one coherent task per branch and one pull request per task while making every mutating Git action explicit.

## Expected Inputs

- Task type and short name.
- Current branch and intended pull request base.
- Changed scope and validation status.
- Explicit approval of each proposed Git mutation batch.

## Normative Documents

1. `CONTRIBUTING.md` is the workflow source of truth.
2. `CLAUDE.md` defines safety and required validation.
3. `STANDARD_POC.md` defines local technical checks.

## Procedure

1. Inspect current branch, worktree status, and relevant remote/base state using read-only capabilities when available.
2. Classify the task as `feature/<name>` or `fixing/<name>` and verify that the scope is coherent.
3. While the `Standard-apps` pull request remains open against `main`, propose `Standard-apps` as the base for dependent work. After it merges, propose rebasing onto `main`.
4. Present a local mutation batch for branch creation and, separately when appropriate, commit creation. Include exact names, included paths, excluded unrelated changes, and validations.
5. Obtain explicit approval before creating a branch or commit.
6. Stage only approved paths and never discard unrelated user changes.
7. Use a short conventional commit message aligned with the task.
8. Treat push, rebase, `--force-with-lease`, pull request creation, and pull request base changes as remote or history-affecting actions requiring a separate explicit confirmation, even when local branch or commit approval already exists.
9. Report the resulting branch, commit, validation evidence, excluded changes, and remaining remote actions.

## Optional Capabilities And Fallbacks

- Without Git execution, return exact proposed commands and stop before mutation.
- Without hosting-service access, provide the pull request title, base, body, and validation summary without claiming a PR exists.
- Without remote-state access, ask the user whether `Standard-apps` is still open before selecting the PR base.
- Without permission for remote actions, keep push, rebase, and PR steps recommended only.

## Validations

- Branch prefix matches task type and contains one coherent task.
- The base branch decision is explicit and supported by current or user-provided state.
- Only approved paths are staged; unrelated changes remain untouched.
- Required checks are executed or clearly listed as blocked/recommended before push or PR.
- Rebase updates use `--force-with-lease`, never an unconditional force push.

## Expected Output

Return an English workflow report containing current state, branch/base decision, approved local mutation batch, commit message, validations, included and excluded paths, remote actions requiring confirmation, and PR draft content when requested.

## Limits

By default this skill may perform only approved local branch and commit actions. It must not push, rebase, force-update, create or edit a PR, merge, reset, or delete branches without a separate explicit confirmation.

## Safety

Never use destructive reset or checkout operations to remove user changes. Never stage secrets, databases, uploads, user data, or generated personal content. Never bypass hooks or validations silently.
