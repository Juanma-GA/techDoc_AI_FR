# Documentation Index

This page is the canonical map of repository documentation. A linked document is authoritative only for the scope stated below.

## Authority Order

1. Live AACF content is the external framework authority.
2. `STANDARD_POC.md` and its linked normative supplements define the technical standard for this repository.
3. `CLAUDE.md` defines local safety, method, and validation instructions.
4. Accepted ADRs record architectural decisions within their stated scope.
5. Procedures, templates, guides, and historical reports are non-normative supporting material.

When live AACF content cannot be fetched, report `AACF NON VERIFIABLE`. Local documents and checks are not AACF evidence.

## Start Here

- [Repository overview](../README.md)
- [Quick start for all apps](../QUICK_START.md)
- [Local working instructions](../CLAUDE.md)
- [Repository technical standard](../STANDARD_POC.md)
- [Contribution and pull request workflow](../CONTRIBUTING.md)
- [Application inventory](apps/README.md)

## Standards And Procedures

- [Local audit report protocol](../PROMPT_AUDIT_STANDARD.md)
- [Profiles, registry, and CI rules](standards/profiles-and-ci.md)
- [Application README template](standards/app-readme-template.md)
- [Demo mode and shared identity integration](standards/demo-mode-integration.md)
- [Backend stacks and optional Tauri desktop](standards/desktop-and-stacks.md)
- [Portable skill contract](standards/portable-skill-contract.md)

## Architecture And History

- [Architecture decision records](adr/)
- [Historical reports](history/README.md)
- [Archived test guide](history/TEST_GUIDE.md)
- [Archived operational validation guide](history/AACF_TESTING_GUIDE.md)

Historical reports preserve context but do not describe the current repository unless explicitly refreshed.

## Automation Interfaces

- [Portable skills](../.github/skills/)
- [Harness-specific agent adapters](../.github/agents/)
- [Compatibility instructions](../AGENTS.md)

Skills are the workflow source of truth. Agent files are compatibility wrappers and must not duplicate the full workflow.
