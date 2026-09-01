---
name: aacf-compliance
description: "Use when: auditing an ATEXIS project against the current external AACF hard rules, language rules, AI safety, design system, governance, or tier controls. Do not use for: local STANDARD_POC compliance, automatic fixes, or claims based only on repository documents."
---

# AACF Compliance

## Purpose And Non-Goals

Perform a factual, read-only compliance audit against current external AACF content. Keep this workflow strictly separate from local repository standard checks.

## Expected Inputs

- Repository or project scope.
- Requested AACF domains or full-audit intent.
- Access to an authoritative AACF source when available.

## Normative Documents

The current external AACF version and documents are the only normative sources for an AACF verdict. Depending on scope, obtain:

- AACF `VERSION`;
- hard rules;
- applicable language rules;
- AI output safety rules for AI, agent, prompt, or LLM work;
- design system and branding for UI work;
- governance, guardrails, and tier checklists for audit readiness.

Local `STANDARD_POC.md`, `CLAUDE.md`, scripts, guides, adapters, and historical reports may provide supplementary project context only.

## Procedure

1. Identify the requested repository and audit scope.
2. Attempt to obtain the current AACF version from an approved authoritative channel before inspecting project compliance.
3. Obtain only the AACF documents needed for the scope and record their version or freshness evidence.
4. If the authoritative source is inaccessible or its version cannot be established, set the verdict to `AACF NON VERIFIABLE`; do not guess current rules from summaries or local copies.
5. When AACF is verifiable, inspect only source, configuration, manifests, tests, and documentation needed to establish evidence.
6. Map each finding to an AACF rule identifier and classify severity as critical, high, medium, or low.
7. Separate confirmed violations from unverified controls and unrelated local-standard observations.
8. Return a remediation backlog without applying changes.

When the verdict is `AACF NON VERIFIABLE`, do not compare the project with remembered, summarized, previously fetched, or allegedly "known" AACF principles. List only the authoritative documents that are missing and keep local observations in a separate, explicitly non-AACF section.

## Optional Capabilities And Fallbacks

- Any approved API, MCP tool, web interface, exported bundle, or human-provided authoritative document may supply AACF content; no named tool is required.
- If live retrieval is unavailable, ask whether the user can provide a current authoritative export. Otherwise return `AACF NON VERIFIABLE` and list the missing documents.
- Without repository search, inspect user-provided files and known project paths; mark uncovered controls unverified.
- Without command execution, omit automated checks and list them as supplementary recommendations.

## Validations

- Verify AACF version or freshness before issuing any compliant or non-compliant AACF verdict.
- Record authoritative documents consulted.
- Reject statements that no local rule conflicts with AACF when current AACF content was not verified.
- Ensure every finding cites an AACF rule and project evidence.
- Confirm that local standards are not presented as AACF proof.
- Confirm that no remediation was applied.

## Expected Output

Return an English report in this order:

1. Scope and evidence.
2. Executive verdict: `COMPLIANT`, `COMPLIANT WITH EXCEPTIONS`, `NOT COMPLIANT`, or `AACF NON VERIFIABLE`.
3. Findings ordered by severity.
4. Unverified controls.
5. Remediation backlog.
6. Supplementary local observations, clearly separated when present.

## Limits

No AACF verdict is valid without a verified current external source. This skill is not the local `audit-standard` workflow and cannot silently fall back to it.

## Safety

Never read databases, SQLite files, `backend/data`, storage, uploads, user-provided files unless explicitly supplied for the audit, secrets, API keys, or generated personal data. Never edit, delete, rename, reset, commit, install, deploy, or migrate. Never disclose credentials used to access AACF.
