# Documentation Index

This page is the canonical map of repository documentation. A linked document is authoritative only for the scope stated below.

## Authority Order

1. Live AACF content is the external framework authority.
2. The pinned framework's [`STANDARD_POC.md`](../framework/STANDARD_POC.md) and
   linked normative supplements define the reusable technical baseline.
3. This repository's [`STANDARD_POC.md`](../STANDARD_POC.md) is the effective
   TECHDOC_AI standard: it adapts that baseline to the consumer's paths,
   registry, ports, and integrations. Framework updates do not alter it
   automatically; reconcile it when the submodule pointer changes.
4. `CLAUDE.md` defines local safety, method, and validation instructions.
5. Accepted ADRs record architectural decisions within their stated scope.
6. Procedures, templates, guides, and historical reports are non-normative
   supporting material unless the effective standard explicitly makes them normative.

When live AACF content cannot be fetched, report `AACF NON VERIFIABLE`. Local documents and checks are not AACF evidence.

## Start Here

- [Repository overview](../README.md)
- [Quick start for all apps](../QUICK_START.md)
- [Local working instructions](../CLAUDE.md)
- [Effective TECHDOC_AI standard](../STANDARD_POC.md)
- [Contribution and pull request workflow](../CONTRIBUTING.md)
- [Application inventory](apps/README.md)

## Standards And Procedures

- [Pinned framework technical baseline](../framework/STANDARD_POC.md)
- [Framework consumption and document ownership](../framework/docs/standards/consuming-framework.md)
- [Shared audit protocol entrypoint](../PROMPT_AUDIT_STANDARD.md)
- [Profiles and app registry](standards/profiles-and-registry.md)
- [Application README template](standards/app-readme-template.md)
- [Demo mode and shared identity integration](standards/demo-mode-integration.md)
- [Design system: tokens, fonts, shared UI and guardrails](standards/design-system.md)
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

## Ownership Boundaries

The root `README.md`, `QUICK_START.md`, `CONTRIBUTING.md`, `CLAUDE.md`,
package manifests, lockfile, workspace configuration, TypeScript base
configuration, app registry, port assignments, and app inventory belong to
TECHDOC_AI. Same-named framework documents describe the framework repository,
not this consumer.

Consumer guides with a framework counterpart are explicitly labeled as local
adaptations and link to the pinned source. Identical guides use a root pointer
instead of a second checklist. `framework/docs/standards/consuming-framework.md`
defines how to reconcile those adaptations when updating the submodule.
