# Contributing

This repository uses one coherent task per branch and one pull request per task.

## Branches

- Use `feature/<name>` for features and documentation additions.
- Use `fixing/<name>` for corrections.
- Do not work directly on `main` unless that choice is explicit.
- While the `Standard-apps` pull request targets `main`, base related work on `Standard-apps`.
- After `Standard-apps` is merged, rebase open branches onto `main` and update them with `--force-with-lease`.

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
