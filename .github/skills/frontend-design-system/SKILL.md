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
4. `docs/standards/design-system.md` (token pipeline, utilities, fonts, light palette, shared primitives, guardrails) and ADR 0005.
5. `framework/design-tokens/tokens.json` and existing `@internal/ui` patterns.
6. Application-specific README deviations and accepted ADRs.

## Procedure

1. Identify the user workflow, current component ownership, and applicable app scope.
2. Determine whether the change is app-specific, a reusable `@internal/ui` primitive, or a design-token change.
3. Inspect neighboring established patterns before proposing new components or tokens.
4. Present a mutation batch with affected paths, UI states, i18n keys, responsive behavior, accessibility behavior, and validations.
5. Flag any `framework/packages/ui` or `framework/design-tokens` edit as cross-application and obtain explicit approval for that shared impact.
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
- Token edits happen in `framework/design-tokens/tokens.json` only, followed by `pnpm tokens:build`; `theme.css` is generated and never edited by hand. `pnpm tokens:check` and `pnpm --filter @internal/design-tokens test` (theme sync + WCAG contrast for both themes) pass.
- Active/selected states use `--color-nav-active-bg`/`--color-nav-active-fg` (soft tint in light, solid blue in dark); a printable or exported "white page" uses `card.base`, not the tinted light `bg.base`.
- Fonts and theme variables come only from `@import "@internal/design-tokens/base.css"` at the top of the app `index.css`: no app-level `@fontsource/*` dependency or import, no Google Fonts `<link>`, and CSS uses `var(--font-sans|mono|display)` instead of literal font names.
- Before writing a local component, check the shared primitives in `docs/standards/design-system.md` §5 (`PageHeader`, `FormField`, `CollapsibleSection`, `Alert`, `Tabs`, `Table`, `Tooltip`, `Skeleton`, `LlmSettingsPanel`, `DemoModeSettingsCard`, ...).
- New or reworked Settings pages use `LlmSettingsPanel` for the Mistral block (app-specific LLM options go in its `children`, extra models via `modelFields`) and `DemoModeSettingsCard` for the operating mode, instead of local forms.
- Text or icons on a `bg-brand`/`bg-danger` fill use `text-brand-fg`, never `text-fg`. Opacity modifiers (`bg-success/15`) are allowed on hex tokens only.
- Dark and light themes, FR and EN, keyboard use, focus, loading, error, empty, disabled, and optimistic states are covered when applicable.
- Brand marks and favicons are app-owned or supplied by an optional integration. The framework core must not require a specific company logo; see `docs/standards/demo-mode-integration.md`.
- For apps with the `llm` profile, the LLM settings (key, base URL, models, connection test) must sit in a collapsible section of Settings, collapsed by default once configured, with an accessible toggle (`aria-expanded`) and FR/EN labels. The models available from the provider (returned by the connection test, `models` field of `POST /api/v1/settings/test`) must be listed and selectable for the chat, embedding and vision model fields rather than typed blind; free text stays possible when the list is empty.
- No hardcoded hex, raw machine tokens, prohibited UI libraries, browser alerts, or Unicode icons are introduced.
- `bash scripts/check_standard.sh` design-system checks 18-22 pass (generated theme, no font CDN, `var(--font-*)` only, `base.css` + `color-scheme` in every frontend, no `.ui-*` overrides in app CSS).
- Frontend build, typecheck, lint, Vitest, and Playwright status is recorded as executed or recommended.

## Expected Output

Return an English report with user workflow, ownership decision, approved mutation batch, UI states, files changed, shared impact, validations, visual evidence, unverified behavior, and residual risk.

## Limits

Do not redesign unrelated screens, add a competing component library, change shared tokens for one local preference, or claim visual correctness without browser evidence.

## Safety

Never expose user documents, uploaded content, secrets, or production data in fixtures or screenshots. Use synthetic fixtures. Never modify files before explicit batch approval.
