---
name: git-pr-workflow
description: "Use when: creating or switching Git branches, using worktrees, syncing a feature branch with main, committing, pushing, or creating/updating a pull request in this monorepo. Do not use for: destructive history rewrites, force-pushes, or unrelated tasks."
---

# Git And Pull Request Workflow

## Purpose And Non-Goals

Keep one coherent task per branch and one pull request per task. Complete explicitly requested Git actions promptly without asking for the same approval twice.

This skill does not authorize destructive history changes, force-pushes, branch deletion, or work on `main` without an explicit request.

## Expected Inputs

- The requested action: branch/worktree creation, branch sync, commit, push, or pull request.
- The task's relevant changes and, when needed, the intended branch or worktree path.
- Validation status for changes being committed or published.

Infer details from the current task and Git state when clear. Ask only when ambiguity affects the target, mixes unrelated work, or could risk user changes.

## Normative Documents

1. `CONTRIBUTING.md` defines the repository branch, worktree, commit, validation, and pull request workflow.
2. `CLAUDE.md` defines repository safety and required validation.
3. `STANDARD_POC.md` and the relevant app documentation define technical requirements for application changes.

## Procedure

1. **Inspect once, narrowly.** Check `git status --short --branch`, the current branch, and `git worktree list` when worktrees affect the task. Inspect only the relevant diff and paths. Do not repeat checks whose state has not changed.
2. **Choose the right branch.**
   - Use `feature/<name>` for features and documentation additions; use `fixing/<name>` for corrections.
   - Start independent work from the latest `origin/main`.
   - Start dependent work from the parent PR branch. After that PR merges, merge `origin/main` into the dependent branch as documented in `CONTRIBUTING.md`.
   - Do not commit on `main` unless the user explicitly asks to.
3. **Handle worktrees without disturbing another checkout.**
   - Check `git worktree list` before creating or switching a branch. If the target branch is already checked out elsewhere, use that worktree or ask before moving it; never force a checkout.
   - For a new independent worktree, fetch and create its branch from `origin/main`:

     ```text
     git fetch origin
     git worktree add -b feature/<name> "C:\path\to\worktree" origin/main
     ```

   - For an existing branch, create a worktree for it:

     ```text
     git worktree add "C:\path\to\worktree" feature/<name>
     ```

   - For dependent work, create the new worktree from the parent branch, or use `git switch -c feature/<name>` in the parent worktree when the user wants to continue there.
   - To move the current branch out of the primary worktree, first confirm it is clean, switch that worktree to `main`, then add a worktree for the now-free feature branch. Use quoted Windows paths and verify with `git worktree list`.
4. **Treat the requested operation as approval for that operation.** A direct request such as “commit this” or “commit and push” authorizes the named action(s); do not ask for a second confirmation. Do not infer permission to commit or push from “fix this”, “prepare”, or a request that only asks for advice. A request to sync a branch authorizes the documented local merge; push only when the user asks to push or publish.
5. **Keep scope precise.** Stage only files belonging to the current task. Never stage all changes blindly. If changes contain multiple unrelated tasks or the requested commit scope is unclear, ask which paths to include. Never stage secrets, databases, uploads, user data, or generated personal content.
6. **Validate efficiently.**
   - Before a commit, run `bash scripts/check_standard.sh` unless it has already passed after the latest relevant changes.
   - Before pushing application changes, run the applicable checks from `CONTRIBUTING.md`. Reuse successful checks for unchanged files; do not run unrelated app checks for documentation-only changes.
   - If a required check fails, report it and do not claim the commit/push is validated. Do not silently bypass it.
7. **Commit and push only what was requested.**
   - Use a short conventional commit message matching the task.
   - Do not create an empty commit when there are no task changes to commit.
   - Push the current feature branch to its configured upstream. If it has no upstream, use `git push -u origin <branch>` when `origin` is the intended remote.
   - Never force-push. If the current branch is `main`, stop unless direct work on `main` was explicitly requested.
8. **Sync a dependent branch after its parent PR merges.** Confirm the worktree is clean, then fetch and merge `origin/main`:

   ```text
   git status --short --branch
   git fetch origin
   git merge --no-commit --no-ff origin/main
   git status
   ```

   Review conflicts before continuing. If Git reports that the branch is already up to date, no merge commit is needed. Otherwise, finish a conflict-free merge with a merge commit; if there are conflicts, stop for resolution rather than committing an incomplete merge. Push only if requested. Follow `CONTRIBUTING.md` for the exact merge commit message and publish steps.
9. **Handle pull requests only when requested.** Use the repository's GitHub workflow and correct base branch (including the parent branch for a dependent PR). Prefer available GitHub tooling; do not require a particular CLI. Never claim a PR was created or updated unless verified.

## Validations

- The current branch, intended base, and worktree are correct for the task.
- Only task-related paths are staged; unrelated work remains untouched.
- `scripts/check_standard.sh` passed after the latest relevant changes before commit.
- Applicable app validations were run before push, or clearly reported as blocked/unverified.
- A dependent branch was updated from `origin/main` only after its parent PR merged; conflicts were reviewed before committing.
- Push and PR actions match the user's explicit request and target branch.

## Expected Output

Respond in the user's language and keep routine Git reports concise. State the branch, files included (and any excluded unrelated changes), commit hash/message when created, push result, validations actually run, and PR link when applicable. Clearly identify anything blocked or not verified.

## Limits And Fallbacks

- If Git or hosting-service access is unavailable, provide the exact commands and label them as not executed.
- If the remote, target branch, worktree, commit scope, or conflict resolution is uncertain, stop only that operation and ask a focused question.
- Do not claim remote state, successful validation, or PR status without checking it.

## Safety And Data Handling

- Never discard user changes or use destructive reset/checkout commands.
- Never rebase, force-push, delete branches, or bypass hooks/validations unless the user explicitly requests the specific operation; still explain material risks before a destructive history rewrite.
- Never read or commit application databases, uploaded files, user storage, secrets, API keys, or generated personal data.
- Leave unrelated worktree changes untouched.
