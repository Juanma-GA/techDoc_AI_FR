# AACF Add-on: Local-First POC Profile

**Status:** Proposed integration package; not an AACF rule or approval.
**Source reviewed:** Local AACF snapshot `2.0.0`. The deployed version could not be verified because the `aacf_fetch` MCP tool was unavailable.

## Purpose

This package describes the ATEXIS monorepo workflow for developer-only, local-first proof-of-concept applications. It adds the repository organization, app-instantiation workflow, Windows launchers, conditional frontend builds, and optional ZIP packaging that are not covered by the reviewed AACF templates.

It is not a second design system, a security standard, or a replacement for AACF's web-app/internal-tool templates. AACF rules and tier controls remain authoritative. This profile must not be used for shared, client-facing, or production applications.

## Duplication Check

| Concern | Already covered by AACF | Add-on treatment |
|---|---|---|
| Global tokens, branding, components, accessibility, responsive UI | `styles/design-system.md`, `styles/branding.md`, `styles/ui-kit.md` | Keep AACF authoritative. The exact local token catalog and UX proposal are documented in [DESIGN.md](DESIGN.md); approve/map them before adoption. |
| Localization, humanized text, browser state, mutation UX | Hard Rules HR1, HR15, HR20, HR21 | Inherit these rules; record local conflicts below instead of restating or weakening them. |
| Security, authentication, data, tiers, governance | Hard Rules, `governance/`, and the existing templates | No exceptions are granted by this package. |
| Generic web-app and internal-tool structure | `templates/web-app.md`, `templates/internal-tool.md` | Add only the local monorepo lifecycle and launcher details. |
| Monorepo app ownership, template instantiation, `.bat` launch/build/package behavior | Not specified in the reviewed AACF files | This is the primary new material in `PROFILE.md`. |

## Adoption Blockers

The local POC standard and the reviewed AACF snapshot contain policy differences. AACF owners must resolve these before adopting the profile as normative; this package does not resolve them by assertion.

| Topic | Local POC convention | AACF snapshot concern | Required decision |
|---|---|---|---|
| Persistence | SQLite for local-first apps | AACF Hard Rules identify PostgreSQL as the source of truth | Approve a bounded T1 exception or change the local convention. |
| Authentication | No auth for loopback-only T1 apps | AACF auth guidance and web-app/internal-tool templates expect server-side auth / Keycloak | Approve the local-only exception and define its boundary. |
| Browser preferences | Theme/language may be persisted in browser storage | HR1 prohibits persistent browser state; its scope for non-authoritative preferences is unclear | Obtain an AACF owner interpretation; do not persist preferences by default until resolved. |
| Visual identity and implementation | Local blue `#2563eb`, Orbitron, raw JSON/Tailwind tokens, and `@internal/ui` | AACF branding specifies blue `#2E74B5`; AACF specifies DTCG/OKLCH, Style Dictionary, and a private shadcn registry | Approve a scoped variant and map one canonical token/component source before adoption. See [DESIGN.md](DESIGN.md). |
| Tailwind compatibility | Local apps use Tailwind 3.4 | AACF's web-app template specifies Tailwind 4 | Confirm a supported adapter/version and compatibility with the AACF registry. |
| Deployment | Run locally; ZIP packaging is optional | HR5 says code changes must be deployed | Clarify what satisfies HR5 for T1 local-only work and whether packaging is in scope. |
| Destructive actions | Local UI describes a double-click confirmation pattern | HR9 requires explicit, logged confirmation | Keep the pattern only if it meets HR9 and accessibility requirements; otherwise use the approved dialog and audit flow. |

## Source-Repository Findings

- The Windows template uses a short `start.bat` wrapper and `_run.bat`; the latter checks ports, binds to `127.0.0.1`, and conditionally rebuilds the React bundle.
- The template `start.sh` is not behaviorally equivalent: it errors when its default port is occupied and opens `/api/v1/docs` rather than the app root.
- The template React app registers only Home. A Settings page file exists but is not routed; no Data page is present. Treat Home/Data/Settings as target profile screens, not as a complete current scaffold.
- The token comments, CSS theme selectors, standard's default-theme statement, and template's OS-preference startup behavior do not fully agree; [DESIGN.md](DESIGN.md) lists the exact discrepancies.
- The local repository records additional port-assignment deviations in the [application inventory](../apps/README.md).

## Proposed Integration

1. Verify the live AACF version and re-run the duplication/conflict check against that version before merging.
2. Resolve the adoption blockers with AACF maintainers; document any approved T1 exceptions in AACF, not only in a consuming app.
3. Place `PROFILE.md` and `DESIGN.md` under an optional AACF profile location such as `docs/profiles/local-first-poc/`.
4. Add a conditional pointer from AACF `AGENTS.md`: read this profile only when a project explicitly declares the local-first POC scope. Do not make it an always-applied Hard Rule.
5. Keep the existing AACF templates and controls intact for all other application types and tiers.
