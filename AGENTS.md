# Agent Compatibility Guide

This file is a harness compatibility entry point. It does not duplicate the repository standards or the external AACF.

## Authority

1. Fetch the current AACF from its approved external source when available. AACF has priority over local repository rules.
2. Use `STANDARD_POC.md` for the normative local technical standard.
3. Use `CLAUDE.md` for local safety, method, and validation instructions.
4. Use `docs/index.md` to locate procedures, templates, ADRs, and historical material.

If the live AACF version or required content cannot be reached, report `AACF NON VERIFIABLE`. Never use local documents or `scripts/check_standard.sh` as proof of AACF compliance.

## Skills And Adapters

Portable workflows live in `.github/skills/<skill-name>/SKILL.md` and are the workflow source of truth. Files under `.github/agents/` are harness-specific wrappers only.

When automatic skill discovery is unavailable, read the relevant `SKILL.md` directly and follow its fallback procedure. Do not infer a workflow from an agent wrapper when the portable skill is present.

## Safety

- Never read application databases, user storage, uploaded files, secrets, API keys, or generated personal data.
- Do not modify legacy content unless the user explicitly approves the scope.
- Ask for confirmation before structural, cross-application, destructive, or mutating workflow changes.
- Separate checks executed from checks merely recommended.

See `docs/standards/portable-skill-contract.md` for the portable format and adapter contract.