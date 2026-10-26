---
name: frontend-design-system
description: "Use when: changing POC UI, shared components, design tokens, Tailwind, themes, i18n, accessibility, or frontend visual consistency. Do not use for: backend-only work, unapproved cross-app changes, or bypassing @internal/ui."
---

# Frontend Design System

## Purpose And Non-Goals

Plan and apply frontend changes through the repository design system while keeping app-local and shared ownership explicit.

## Expected Inputs

- Target application or shared package scope.
- User workflow and desired UI behavior.
- Existing design evidence when relevant.
- Explicit approval of the proposed mutation batch.

## Normative Documents

1. Current AACF design system and branding when accessible.
2. `STANDARD_POC.md` frontend and design-system rules.
3. `CLAUDE.md` shared-component, token, i18n, and structural-change rules.
4. `design-tokens/tokens.json` and existing `@internal/ui` patterns.
5. Application-specific README deviations and accepted ADRs.

## Procedure

1. Identify the user workflow, current component ownership, and applicable app scope.
2. Determine whether the change is app-specific, a reusable `@internal/ui` primitive, or a design-token change.
3. Inspect neighboring established patterns before proposing new components or tokens.
4. Present a mutation batch with affected paths, UI states, i18n keys, responsive behavior, accessibility behavior, and validations.
5. Flag any `packages/ui` or `design-tokens` edit as cross-application and obtain explicit approval for that shared impact.
6. After approval, apply only the listed changes using existing libraries and tokens.
7. Validate all expected states, themes, languages, viewports, loading/error/empty states, and critical interactions.
8. Report executed checks, screenshots or browser evidence when available, and residual visual risk.

Any new shared path or dependency requires a new approved batch.

## Optional Capabilities And Fallbacks

- Without write access, return a component and token change specification.
- Without browser or screenshot capability, provide a manual viewport and interaction checklist and mark visual behavior unverified.
- Without live AACF access, report `AACF NON VERIFIABLE`; do not guess external design rules.
- Without dependency installation, use only verified existing dependencies or stop and report the blocker.

## Validations

- Components come from `@internal/ui`; new primitives live there only with shared-change approval.
- Colors, typography, spacing, and dimensions use approved tokens.
- Dark and light themes, FR and EN, keyboard use, focus, loading, error, empty, disabled, and optimistic states are covered when applicable.
- The shared AI4TECHDOC logo must also appear as the browser tab icon: call `setAi4TechDocFavicon()` from `@internal/ui` once in the frontend entry point (`src/main.tsx`) and do not leave the default Vite icon. Use `Ai4TechDocLogo` rather than copying the asset; see `docs/standards/demo-mode-integration.md`.
- For apps with the `llm` profile, the LLM settings (key, base URL, models, connection test) must sit in a collapsible section of Settings, collapsed by default once configured, with an accessible toggle (`aria-expanded`) and FR/EN labels. The models available from the provider (returned by the connection test, `models` field of `POST /api/v1/settings/test`) must be listed and selectable for the chat, embedding and vision model fields rather than typed blind; free text stays possible when the list is empty.
- No hardcoded hex, raw machine tokens, prohibited UI libraries, browser alerts, or Unicode icons are introduced.
- Frontend build, typecheck, lint, Vitest, and Playwright status is recorded as executed or recommended.

## Expected Output

Return an English report with user workflow, ownership decision, approved mutation batch, UI states, files changed, shared impact, validations, visual evidence, unverified behavior, and residual risk.

## Limits

Do not redesign unrelated screens, add a competing component library, change shared tokens for one local preference, or claim visual correctness without browser evidence.

## Safety

Never expose user documents, uploaded content, secrets, or production data in fixtures or screenshots. Use synthetic fixtures. Never modify files before explicit batch approval.
