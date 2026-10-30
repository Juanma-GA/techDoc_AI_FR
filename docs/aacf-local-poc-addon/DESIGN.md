# Local-First POC UX and Visual Design

**Status:** Proposed local profile; not an AACF-approved design system.
**Evidence:** Current monorepo tokens, shared UI exports, template, and `STANDARD_POC.md`.

## 1. Ownership and Scope

AACF remains the authority for global branding, accessibility, localization, and component governance. This document records the exact local POC design proposal so AACF owners can approve, map, or reject it as an optional profile. It does not authorize a parallel global design system.

The workspace calls its current token set **Midnight Executive**. The values below document the repository implementation; they are not permission to hardcode colors into app code or replace AACF tokens. The source is [tokens.json](../../design-tokens/tokens.json).

## 2. Color Token Catalog

The source is `design-tokens/tokens.json`: `color.*` contains the dark values and `themes.light.color.*` the light overrides. Values are listed here for design review only.

| Token | Dark | Light (v2) |
|---|---|---|
| `bg.base` | `#0e1117` | `#f5f7fb` |
| `bg.2` | `#131720` | `#ffffff` |
| `bg.3` | `#1a2035` | `#eaeef4` |
| `card.base` | `#161c2b` | `#ffffff` |
| `card.hover` | `#1d2540` | `#f1f5f9` |
| `brand.blue` | `#2563eb` | `#2563eb` |
| `brand.blue-light` | `#3b82f6` | `#3b82f6` |
| `brand.fg` | `#ffffff` | `#ffffff` |
| `brand.hover` | `#3b82f6` | `#1d4ed8` |
| `brand.text` | `#3b82f6` | `#1d4ed8` |
| `brand.soft` | `rgba(37,99,235,0.18)` | `rgba(37,99,235,0.10)` |
| `semantic.success` | `#10b981` | `#047857` |
| `semantic.warning` | `#f59e0b` | `#b45309` |
| `semantic.danger` | `#ef4444` | `#b91c1c` |
| `semantic.info` | `#3b82f6` | `#1d4ed8` |
| `accent.teal` | `#06b6d4` | `#0891b2` |
| `accent.purple` | `#8b5cf6` | `#7c3aed` |
| `accent.orange` | `#f97316` | `#ea580c` |
| `accent.pink` | `#ec4899` | `#db2777` |
| `accent.yellow` | `#eab308` | `#ca8a04` |
| `text.base` | `#e2e8f0` | `#0f172a` |
| `text.dim` | `#94a3b8` | `#475569` |
| `text.muted` | `#64748b` | `#64748b` |
| `border.base` | `rgba(255,255,255,0.07)` | `rgba(15,23,42,0.10)` |
| `border.md` | `rgba(255,255,255,0.12)` | `rgba(15,23,42,0.16)` |
| `border.bright` | `rgba(37,99,235,0.4)` | `rgba(37,99,235,0.45)` |
| `surface.sunken` | `#131720` | `#f8fafc` |
| `focus.ring` | `#3b82f6` | `#2563eb` |
| `nav.active-bg` | `#2563eb` | `rgba(37,99,235,0.10)` |
| `nav.active-fg` | `#ffffff` | `#1d4ed8` |
| `overlay` | `rgba(0,0,0,0.6)` | `rgba(15,23,42,0.4)` |

Contrast targets are enforced by `design-tokens/tests/contrast.test.mjs`; see [design-system.md](../standards/design-system.md).

## 3. Token Consumption

- [tokens.json](../../design-tokens/tokens.json) is the repository value source; [theme.css](../../design-tokens/theme.css) is generated from it and exposes CSS variables; [tailwind-preset.ts](../../design-tokens/tailwind-preset.ts) maps semantic utilities to those variables. Apps import `@internal/design-tokens/base.css` (theme variables + self-hosted fonts + document defaults) at the top of their `index.css` and extend the shared Tailwind preset.
- Use semantic utilities such as `bg-bg`, `bg-bg-2`, `bg-card`, `bg-card-hover`, `text-fg`, `text-fg-dim`, `text-fg-muted`, `text-brand-blue-light`, `text-success`, `text-warning`, `text-danger`, `text-info`, `border`, `border-md`, and `border-bright`.
- Use `font-sans`, `font-mono`, `font-display`, `rounded-sm`, `rounded-lg`, `shadow-card`, `w-sidebar-w`, `h-topbar-h`, `text-base`, and `text-label` for their corresponding shared tokens.
- Charts needing theme-aware colors use the shared `colorByTheme(theme, tokenPath)` helper from [design-tokens/index.ts](../../design-tokens/index.ts). Never add app-local hex values or duplicate tokens.
- Before AACF adoption, map this JSON/Tailwind implementation to AACF's canonical token format and registry. Do not maintain two competing sources of truth.

## 4. Typography and Geometry

| Role | Typeface | Weights / size |
|---|---|---|
| Body and general UI | `Inter, sans-serif` | 400, 500, 600, 700; base 13.5px; line-height 1.5 |
| Technical values, code, KPI values, labels | `JetBrains Mono, monospace` | 400, 500, 700 |
| Brand and display headings | `Orbitron, sans-serif` | 500, 700 |
| Compact label | JetBrains Mono, uppercase, muted | `0.6rem`; token line-height 1.2 |

| Geometry token | Value |
|---|---|
| Sidebar width | 252px |
| Top bar height | 52px |
| Main content padding | 24px vertical, 32px horizontal |
| Small radius | 8px |
| Large radius | 12px |
| Card shadow | `0 1px 3px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.2)` |

The dimensions and fonts are current local values, not universal AACF defaults. Fonts are self-hosted and loaded once by `@internal/design-tokens/base.css` (see [design-system.md](../standards/design-system.md)); the shared stacks fall back to system fonts.

## 5. Shared Component Inventory

UI primitives belong in `@internal/ui`; an app must not create a competing local primitive library. The current exports are:

| Group | Components |
|---|---|
| Inputs and atoms | `Badge`, `Button`, `Card`, `Checkbox`, `Input`, `Select`, `Spinner`, `Switch`, `Textarea` |
| Cross-app/business | `ChartCard`, `EmptyState`, `FileDropzone`, `KpiCard`, `LoadingOverlay`, `MarkdownView`, `MultiSelect`, `PortalLink`, `Slicer` |
| Overlays | `Dialog`, `Toast` |
| Shell and utilities | `ThemeToggle`, `ErrorBoundary`, `useMediaQuery`, `cn` |

Use Lucide React icons, not Unicode symbols. Use `Dialog`/`Toast` rather than browser `alert()` or `confirm()`. If a reusable primitive is missing, propose it for the shared package; do not silently recreate it inside an app. The current inventory is exported from [packages/ui/src/index.ts](../../packages/ui/src/index.ts). AACF's component registry remains the authority until maintainers approve a mapping from these exports.

## 6. App Shell and Navigation

The target local POC shell is a persistent navigation sidebar plus a top bar and a scrollable main area. The target sidebar is 252px; the top bar is 52px. At smaller viewports, navigation must remain operable and adapt without horizontal overflow; the exact breakpoint is not currently standardized.

Minimum destinations for the local POC profile are:

| Destination | Purpose |
|---|---|
| Home | App purpose, primary entry point, and backend health status |
| Data | Aggregate data statistics and approved data-management actions |
| Settings | Runtime configuration and capability switches |
| Business destinations | App-specific workflows, added as needed |

The brand name carries a one-sentence localized app description (`app.description`, FR and EN). Theme, language, and applicable capability-status controls belong in the persistent shell. Their exact sidebar/top-bar placement must be consistent across POCs.

## 7. Standard Screens and States

### Home

Show the localized app title/description and backend health from `GET /api/v1/health` as a textual status badge. Provide a clear route into the app's primary workflow. Do not use a machine status slug as display copy.

### Data

Show aggregate statistics from `GET /api/v1/admin/stats` as KPI components. Provide empty, loading, error, and populated states. Offer `POST /api/v1/admin/reset/all` or scoped reset actions only when the app has that capability; preserve `AppConfig` runtime settings and secrets during data resets.

The current local convention arms a destructive button on the first click and executes on a second click within three seconds. This is not automatically AACF-compliant: use an accessible confirmation dialog unless maintainers confirm the local pattern satisfies HR9, including explicit and logged confirmation.

### Settings for an LLM-enabled POC

Use `GET /api/v1/settings`, `POST /api/v1/settings`, and `POST /api/v1/settings/test`. Provide an immediate `llm_enabled` switch; a write-only API key field; base URL, chat model, and embedding model fields; Save and Test Connection actions; and localized success/error feedback. A blank key leaves the saved key unchanged. Never return or display the secret after saving.

Derive the LLM indicator from backend health and use text plus semantic color:

| API state | Semantic i18n key | Example label (FR / EN) | Token |
|---|---|---|---|
| `ok` | `llm.on` | `ON` / `ON` | `success` |
| `untested` | `llm.untested` | `À TESTER` / `UNTESTED` | `warning` |
| `not_configured` | `llm.noKey` | `NO KEY` / `NO KEY` | `warning` |
| `disabled` | `llm.off` | `OFF` / `OFF` | `fg-dim` |

Invalidate/refetch health after saving settings, toggling the capability, or testing the connection. Follow AACF HR20 for known-result mutations: update optimistically and roll back on rejection. Keep pending, disabled, error, and success states visible.

## 8. Theme, Localization, and Accessibility

- The CSS currently sets light values on `:root` and dark overrides on `.dark`. The [template startup script](../../apps/_template/frontend/index.html) honors a saved `theme` preference; if absent, it applies dark mode only when the OS requests dark mode. [ThemeToggle](../../packages/ui/src/components/ThemeToggle.tsx) adds/removes `.dark` and currently persists to `localStorage["theme"]`.
- Persistence of theme/language preferences conflicts with AACF HR1 as currently worded. Until maintainers clarify HR1 or approve an exception, do not persist browser preferences in this profile. A per-session theme control can remain available.
- Localize every visible label, tooltip, empty/error/success message, and icon-only button's accessible name in FR and EN using semantic i18next keys. Never show raw enum/API values. Pass a localized `aria-label` to `ThemeToggle`; its component fallback is currently English.
- Inherit AACF's accessibility bar: WCAG 2.2 AA, keyboard operation, visible focus, real labels, meaningful alt text, sufficient contrast, and reduced-motion support. Do not rely on color alone for statuses.
- Inherit AACF responsive behavior and test desktop and mobile widths. Use shared loading, empty, error, dialog, and toast components where applicable.

## 9. Decisions and Implementation Gaps

| Topic | Local evidence | Required before AACF adoption |
|---|---|---|
| Brand palette | Local blue is `#2563eb`; AACF branding specifies ATEXIS blue `#2E74B5`. | Approve a scoped variant or map to the AACF brand token. |
| Token format | Local raw-hex JSON + Tailwind preset; AACF specifies DTCG/OKLCH + Style Dictionary. | Define one canonical source and a conversion/registry path. |
| Tailwind version | Local apps use Tailwind 3.4; AACF's web-app template specifies Tailwind 4. | Confirm a supported adapter/version and compatibility with the AACF registry. |
| Components | Local `@internal/ui` uses Radix-based components; AACF specifies a private shadcn registry. | Approve the mapping or migrate; do not run competing libraries. |
| Typography | Inter and JetBrains Mono are shared; local Orbitron is an extra display face. All three are self-hosted through `design-tokens/base.css`. | Approve or remove Orbitron. |
| Browser preferences | `ThemeToggle` writes to localStorage. | Resolve HR1 before persisting preferences. |
| Theme defaults | Resolved locally: [theme.css](../../design-tokens/theme.css) is generated from [tokens.json](../../design-tokens/tokens.json) (light `:root`, dark `.dark`) and every template/app starts dark unless `light` was explicitly saved. | Confirm the dark default against AACF. |
| Shell and routes | [App.tsx](../../apps/_template/frontend/src/App.tsx) has a header and Home route only. [Settings.tsx](../../apps/_template/frontend/src/routes/Settings.tsx) is not routed; Data is absent. | Complete and test the target shell before claiming the scaffold implements it. |
| Localization and mutation UX | [Settings.tsx](../../apps/_template/frontend/src/routes/Settings.tsx) has hard-coded copy; [ThemeToggle](../../packages/ui/src/components/ThemeToggle.tsx) fallback label is English; the LLM switch is not optimistic. | Localize all strings/aria names and meet HR20 before claiming AACF alignment. |
| Destructive confirmation | Local double-click pattern is not inherently logged. | Use an approved dialog/audit flow or obtain an explicit HR9 decision. |

This section is intentional: it separates the exact local design proposal from the decisions needed to make it an AACF-approved profile.
