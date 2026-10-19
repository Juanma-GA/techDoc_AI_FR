---
name: release-package
description: "Use when: validating or creating a distributable POC ZIP, checking launchers, conditional frontend builds, bind host, selected port behavior, ZIP contents, or apps/<poc>/dist output. Do not use for: deployment, publishing, packaging user data, or generating a ZIP without dedicated confirmation."
---

# Release Package

## Purpose And Non-Goals

Validate release readiness and, only after dedicated confirmation, generate the repository-standard local POC ZIP.

## Expected Inputs

- Application slug or path.
- Requested validation-only or package-generation mode.
- Expected version or package naming context when required by the app script.
- Dedicated confirmation before ZIP generation.

## Normative Documents

1. `STANDARD_POC.md` launcher and packaging rules.
2. `CLAUDE.md` conditional build, dependency-install guard, output, and data-safety rules.
3. The application's README, launchers, and declared packaging entry point (`.py` for FastAPI, `.mjs` for PDF Toolkit Go).
4. `docs/apps/README.md` for target default port policy.

## Procedure

1. Verify that the app path, launchers, rebuild helper, packagers, packaging script, frontend manifest, and expected dist paths exist.
2. Inspect the declared default port, localhost bind, free-port behavior, conditional frontend rebuild, and `node_modules` install guard.
3. Verify that the packager preserves a valid existing frontend dist when a rebuild fails and always targets `apps/<poc>/dist/`.
4. Build a release-readiness matrix covering source checks, backend tests, frontend checks, browser smoke tests, and package inspection.
5. If any required check is blocked or failing, report the blocker and do not silently downgrade the package.
6. Before any command that creates or replaces a ZIP or build artifact, present the exact command, output path, likely artifacts, and exclusions; request dedicated confirmation.
7. After confirmation, run only the declared repository packaging entry point.
8. Inspect package entry names and metadata without opening user files. Confirm required runtime files and absence of prohibited data.
9. Report the final path, package checks, failures, and residual risk.

## Optional Capabilities And Fallbacks

- Without execution, provide a validation matrix and exact repository-declared packaging command as recommended.
- Without archive inspection, mark contents unverified and do not issue a ready verdict.
- Without frontend tooling, an existing valid dist may be used only when the repository packager explicitly supports and reports that behavior.
- Without write permission, remain in validation-only mode.

## Validations

- Launcher defaults and free-port behavior match the target policy.
- Bind remains `127.0.0.1` and the chosen port is printed and opened.
- Frontend rebuild is conditional; dependency installation occurs only when `node_modules` is absent.
- ZIP output is under `apps/<poc>/dist/` and includes required launchers and runtime assets. FastAPI packages carry source, frontend dist and embedded Python; PDF Toolkit web packages carry the Windows x64 Go toolchain, allowlisted backend source, vendored dependencies, built UI, documentation and licenses. They compile offline at first launch and reuse the binary conditionally. Do not require Python in a Go package or promise that local compilation bypasses endpoint protection.
- Optional Tauri installers retain the web workflow. Verify the backend resource, startup health/error handling, installed paths and child shutdown; use the app's `package.bat desktop` output policy.
- ZIP excludes databases, data, storage, uploads, secrets, virtual environments, caches, and unrelated apps.
- Executed and recommended checks are separate.

## Expected Output

Return an English release report with mode, readiness matrix, dedicated approval record, command executed, output path, archive checks, exclusions, blocked checks, and verdict.

## Limits

This skill produces a local distributable package, not a cloud deployment or release publication. It never changes versions or source files unless separately approved.

## Safety

Never include or inspect user databases, storage, uploads, documents, secrets, API keys, or generated personal data. Never create a ZIP without dedicated confirmation. Never overwrite an unrelated artifact.
