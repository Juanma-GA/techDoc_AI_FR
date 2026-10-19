# Contributing

This repository uses one coherent task per branch and one pull request per task.

## Branches

- Use `feature/<name>` for features and documentation additions.
- Use `fixing/<name>` for corrections.
- Do not work directly on `main` unless that choice is explicit.
- For an independent feature, start from the latest `origin/main`:

  ```bash
  git status
  git fetch origin
  git switch -c feature/<name> origin/main
  ```

- For a feature that depends on an open pull request, make sure the parent PR's source branch is checked out, then create the new branch from the current branch:

  ```bash
  git status --short --branch
  git switch -c feature/<name>
  ```

  The new branch inherits the current branch's commits, so it remains dependent on that PR until the parent is merged.

- After the parent PR is merged into `main`, update the dependent branch by merging `origin/main` into it:

  ```bash
  git status --short --branch
  git fetch origin
  git merge --no-commit --no-ff origin/main
  git status
  ```

  Review the status and resolve any conflicts. If conflicts occurred, stage the resolved files with `git add <resolved-files>`. Then finish and publish the merge:

  ```bash
  git commit -m "Merge origin/main into <branch-name>"
  git push origin <branch-name>
  ```

## Before a Push or Pull Request

Run the validations relevant to the changed scope. At minimum, run:

```bash
bash scripts/check_standard.sh
```

For application changes, also run the applicable backend tests, frontend build, typecheck, lint, Vitest, Playwright smoke test, and packaging validation. Record checks that were executed separately from checks that remain recommended.

Never read or commit user databases, uploaded files, generated user content, secrets, or files under application data and storage directories.

## Commits

Use short conventional commit messages, for example:

- `docs: define repository documentation hierarchy`
- `feat: add onboarding and audit skills`
- `fix(ui): correct settings status refresh`

Keep documentation hierarchy, skills, application documentation, and legacy cleanup in separate commits when practical.

## Pull Requests

- Keep the pull request limited to one task.
- State the normative documents used for the change.
- List validations executed and their results.
- List unverified checks and known deviations.
- Do not claim AACF compliance when the live AACF source was unavailable.
