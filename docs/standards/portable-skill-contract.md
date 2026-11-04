# Portable Skill Contract

TECHDOC_AI adaptation of the [framework contract](../../framework/docs/standards/portable-skill-contract.md).
The framework owns reusable skill guidance; this file records consumer
discovery and synchronization requirements.

Portable skills live at `.github/skills/<skill-name>/SKILL.md`. A skill is the workflow source of truth; harness-specific agents and prompts are thin compatibility adapters.

## Required Frontmatter

```yaml
---
name: skill-name
description: "Use when: explicit trigger phrases. Do not use for: explicit exclusions."
---
```

- `name` must exactly match the parent directory name.
- `description` must state explicit triggers and exclusions.
- Portable frontmatter must not declare harness-specific tools, agents, models, or UI metadata.

## Required Sections

Every skill must define:

1. Purpose and non-goals.
2. Expected inputs.
3. Normative documents to consult and their authority order.
4. Procedure.
5. Validations.
6. Expected output.
7. Limits and unverified states.
8. Safety and data-handling rules.

## Portability Rules

A portable skill must not require:

- `aacf_fetch` or any specific MCP server;
- `gh` or another hosting CLI;
- a terminal or shell;
- VS Code or another editor;
- permission to write, rename, delete, commit, install, deploy, or migrate.

Capabilities may be described as optional. For each optional capability, the skill must define a manual or read-only fallback and clearly label anything not executed or verified.

Mutation skills must request explicit confirmation before changes. They must still be useful in read-only mode by returning a proposed change set and validation plan.

## Normative Sources

- External AACF is authoritative for AACF controls when its current version and content are accessible.
- `STANDARD_POC.md` is authoritative for local repository technical compliance.
- `PROMPT_AUDIT_STANDARD.md` defines the local audit report format.
- Operational testing guides are procedures, not normative sources.

Never substitute a local document for unavailable AACF content. Return `AACF NON VERIFIABLE` when the external authority cannot be checked.

## Safety

- Never read application databases, uploaded files, user storage, secrets, API keys, or generated personal data.
- Inspect only source code, configuration, schemas, migrations, tests, documentation, and file names needed for the task.
- Never expose personal paths or secret values in output.
- Never delete persistent or user data.
- Separate confirmed evidence, inferred risk, and unverified controls.

## Validation

For every skill:

- parse the YAML frontmatter;
- verify that the folder name equals `name`;
- verify required sections and explicit fallback behavior;
- check links and repository-relative paths;
- scan for personal paths and secret-like values;
- confirm that prohibited data locations are excluded;
- test discovery manually when automatic discovery is unavailable.

Read-only skills must be trialed against `framework/apps/_template` and `apps/ocr-vision`. Record the harness used, actions actually executed, fallbacks used, and any portability gaps.

## Adapter Contract

An adapter may declare harness-specific tools and invocation metadata. Its body must point to the portable skill, preserve the skill's safety boundaries, and add only the minimum instructions needed to load and run it. If the skill cannot be discovered automatically, the adapter must instruct the harness to read `.github/skills/<skill-name>/SKILL.md` directly.
