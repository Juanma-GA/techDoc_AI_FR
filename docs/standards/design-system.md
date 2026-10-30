# Design System Supplement

Normative supplement to [`STANDARD_POC.md`](../../STANDARD_POC.md) §5 for the shared visual framework: `design-tokens/`, `@internal/ui`, the app template and the guardrails in `scripts/check_standard.sh`. Decision record: [ADR 0005](../adr/0005-design-system-v2.md).

Live AACF design rules take precedence. When they cannot be fetched, report `AACF NON VERIFIABLE`; this document is local evidence only.

## 1. Token Pipeline

```text
design-tokens/tokens.json  --(pnpm tokens:build)-->  design-tokens/theme.css   (CSS variables)
            |                                                |
            +--> tailwind-preset.ts (utilities)  <-----------+
            +--> index.ts (JS/TS: color, colorByTheme, shadowByTheme, currentTheme)
```

| File | Role | Edit? |
|---|---|---|
| `tokens.json` | Only source of values. `color.*` = dark palette (default theme), `themes.light.color.*` / `themes.light.shadow.*` = light overrides, plus static tokens (`font`, `fontSize`, `lineHeight`, `radius`, `shadow`, `motion`, `layout`). Validated by `tokens.schema.json`. | Yes |
| `theme.css` | **Generated** by `design-tokens/scripts/build-theme.mjs`. `:root` = light palette + static tokens, `.dark` = dark palette. | Never by hand |
| `tailwind-preset.ts` | Maps utilities to the generated variables. | When adding a utility |
| `index.ts` | JS access for charts/canvas/SVG that cannot read CSS variables. | When adding a helper |

Commands:

```text
pnpm tokens:build    # regenerate theme.css after editing tokens.json
pnpm tokens:check    # fails when theme.css is stale (also run by check_standard.sh)
pnpm --filter @internal/design-tokens test
```

### CSS variables emitted

| Variable | Content | Example |
|---|---|---|
| `--color-<path>` | Full color, backward compatible | `--color-semantic-success: #10b981` |
| `--color-<path>-rgb` | Channels for hex tokens only | `--color-semantic-success-rgb: 16 185 129` |
| `--shadow-<name>` | Themed shadow | `--shadow-card` |
| `--font-<sans\|mono\|display>` | Font stack with system fallbacks | `--font-display` |
| `--font-size-<name>`, `--line-height-<name>` | Typography scale | `--font-size-page-title` |
| `--radius-<xs\|sm\|md\|lg\|xl\|full>` | Radius scale | `--radius-lg` |
| `--motion-<name>` | Durations and easing | `--motion-duration-fast` |
| `--sidebar-w`, `--topbar-h` | Layout | |

`<path>` joins the JSON path with dashes: `color.brand.blue-light` becomes `--color-brand-blue-light`.

### Tailwind utilities

| Need | Utility |
|---|---|
| Backgrounds | `bg-bg`, `bg-bg-2`, `bg-bg-3`, `bg-card`, `bg-card-hover`, `bg-surface-sunken`, `bg-overlay` |
| Text | `text-fg`, `text-fg-dim`, `text-fg-muted`, `text-brand-text` |
| Brand fills | `bg-brand` + `text-brand-fg`, `hover:bg-brand-hover`, `bg-brand-soft` |
| Status | `text-success`, `bg-warning/15`, `border-danger/40`, `text-info` |
| Borders | `border` (default), `border-md`, `border-bright` |
| Focus | `ring-2` (defaults to `focus.ring`) or `ring-focus` |
| Shadows | `shadow-card`, `shadow-popover` |
| Typography | `font-sans`, `font-mono`, `font-display`, `text-base`, `text-label`, `text-card-title`, `text-page-title` |
| Radius | `rounded-xs`, `rounded-sm`, `rounded-lg` (tokens); `md`/`xl` keep Tailwind defaults for compatibility |
| Motion | `duration-fast`, `duration-base`, `ease-standard` |

Rules:

- Hex tokens accept opacity modifiers (`bg-success/15`). Tokens already defined with an alpha (`border.*`, `brand.soft`, `overlay`) do not.
- Text or icons on a `brand`/`danger` fill use `text-brand-fg`, never `text-fg` (dark in light mode).
- An unknown token name in `tailwind-preset.ts` throws at build time.

### Adding or changing a token

1. Edit `tokens.json` (dark value under `color.*`, light override under `themes.light.color.*` when it differs).
2. Run `pnpm tokens:build`, then `pnpm --filter @internal/design-tokens test`.
3. Expose a utility in `tailwind-preset.ts` only when components need it.
4. Document the token here. Token changes are cross-application: they need explicit approval (see `CLAUDE.md`).

## 2. Backward Compatibility

- Every legacy variable (`--color-bg-base`, `--color-text-dim`, `--color-border-md`, ...) keeps its name and still holds a full color. App CSS written against `var(--color-*)` keeps working.
- `color.*`, `colorByTheme`, `font`, `radius`, `shadow`, `layout` exports of `@internal/design-tokens` keep their shape. New exports are additive.
- Existing Tailwind utilities keep their names; they now also support opacity modifiers.
- The test `design-tokens/tests/theme.test.mjs` guards the legacy variables and the light/dark key parity.

## 3. Palettes And Contrast

Dark remains the default theme (`.dark`, applied by the anti-flash script). Light v2 (October 2026) replaces the flat white light theme:

| Role | Light token | Value | Intent |
|---|---|---|---|
| App background | `bg.base` | `#f5f7fb` | Slightly tinted so white cards stand out |
| Sidebar / recessed panels | `bg.2` | `#f8fafc` (unchanged) | Kept for compatibility: apps use `bg-2` for recessed panels (KPI, code); the sidebar is separated by its border |
| Recessed areas | `bg.3` | `#eaeef4` | Tracks, inactive switches |
| Cards / hover | `card.base` / `card.hover` | `#ffffff` / `#f1f5f9` | |
| Text | `text.base` / `dim` / `muted` | `#0f172a` / `#475569` / `#64748b` | AA for body and secondary text |
| Status text | `semantic.*` | 700 shades (`#047857`, `#b45309`, `#b91c1c`, `#1d4ed8`) | AA as text on white |
| Brand | `brand.blue` / `hover` / `text` | `#2563eb` / `#1d4ed8` / `#1d4ed8` | Hover darkens in light, lightens in dark |
| Active navigation | `nav.active-bg` / `nav.active-fg` | `brand.soft` tint / `#1d4ed8` | Light uses a soft tint; dark keeps the solid blue pill |
| Borders | `border.base` / `md` | `rgba(15,23,42,.10)` / `.16` | Slate-tinted, visible on tinted backgrounds |
| Shadow | `shadow.card` | two light slate layers | Dark keeps its deeper shadow |

Dark `text.muted` moved from `#4b5563` to `#64748b` (it was 2.3:1 on cards).

`design-tokens/tests/contrast.test.mjs` enforces WCAG ratios for both themes: body text 7:1, secondary text 4.5:1, muted text 3:1, text on brand 4.5:1, active navigation 4.5:1, status colors 3:1 (4.5:1 in light). A palette change that breaks a ratio fails `pnpm --filter @internal/design-tokens test`.

Compatibility notes:

- Code that used the light `bg.base` as a "white page" color must use `card.base` instead (done for flowchart-generator printable exports).
- Shared shell CSS reads `--color-nav-active-*`, `--color-brand-text` and `--color-focus-ring`; app CSS should do the same rather than `--color-brand-blue` + `--color-text-base` for active states.

## 4. Fonts And Base Stylesheet

Every app has exactly one design-system import, at the top of `frontend/src/index.css`:

```css
@import "@internal/design-tokens/base.css";

@tailwind base;
@tailwind components;
@tailwind utilities;
```

`base.css` imports, in order:

1. `theme.css` (generated variables, `color-scheme` per theme);
2. `fonts.css` (self-hosted `@fontsource` faces: Inter 400/500/600/700, JetBrains Mono 400/500/700, Orbitron 500/700);
3. document defaults: `html` font stack, 13.5px base size, line-height, themed background/text, font smoothing, `#root` full height, themed `::selection` and `:focus-visible`, mono `code`, and the `.label` class.

Rules:

- Apps never declare `@fontsource/*` dependencies, never `@import "@fontsource/..."`, and never load `fonts.googleapis.com` / `fonts.gstatic.com` (local-first, offline-capable, no third-party request).
- CSS uses `var(--font-sans)`, `var(--font-mono)`, `var(--font-display)`; never a literal font name outside `design-tokens/`.
- Fonts use `font-display: swap`; the stacks fall back to `system-ui` / `Segoe UI` / `Consolas` while loading or if a face is missing.
- `@import "@internal/design-tokens/theme.css"` alone remains supported for compatibility, but then the app must load fonts itself; migrate to `base.css`.

## 5. Shared Primitives

All primitives come from `@internal/ui`, use tokens only, support both themes and keyboard focus (`ring-focus`), and ship with a Vitest file.

| Need | Primitive | Notes |
|---|---|---|
| Page title + description + actions | `PageHeader` | Orbitron title (`text-page-title`), optional `eyebrow`, actions wrap on mobile. Keeps the legacy `page-header` class names. |
| Labeled form control | `FormField` | Wires `htmlFor`/`id`, `aria-describedby` (hint/error), `aria-invalid`, `aria-required`; sets `state="error"` on `Input`/`Select`/`Textarea`. |
| Optional or advanced block | `CollapsibleSection` | Disclosure button with `aria-expanded`/`aria-controls`; controlled or uncontrolled. Use it for the LLM settings block (collapsed once configured). |
| Inline information / warning / error | `Alert` | `info`/`success`/`warning`/`danger`; `danger` uses `role="alert"`. |
| Views within a page | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` | Radix: arrow keys, roving focus. Always give `TabsList` an `aria-label`. |
| Tabular data | `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`, `TableCaption` | Scroll container with border; `data-state="selected"` rows use `brand.soft`. |
| Hint on hover/focus | `Tooltip` (or `TooltipRoot`/`TooltipTrigger`/`TooltipContent`) | Child must be focusable; icon-only buttons still need `aria-label`. |
| Loading placeholder | `Skeleton` | `aria-hidden`; respects `prefers-reduced-motion`. Pair with a `role="status"` label for screen readers. |
| Empty list | `EmptyState` | |
| Blocking action confirmation | `Dialog` | Never `alert()`/`confirm()`. |
| Transient feedback | `Toast` | Opaque card with a colored left edge per variant. |

Shared component conventions (v2):

- `Button` `primary`/`danger` text uses `text-brand-fg`; hover uses `brand.hover` (darker in light, lighter in dark); focus ring has an offset.
- `Input`/`Select`/`Textarea` sit on `surface.sunken`, focus with a brand border plus a soft ring; the `error` state keeps the danger border on focus.
- `Card`, `EmptyState`, `CollapsibleSection`, `Table` use `rounded-lg` (token 12px) and `shadow-card`; overlays use `shadow-popover` and `bg-overlay`.
- `Switch`/`Checkbox` use `ring-focus`, `border-md`, and `brand.fg` for the checked knob/check mark.

## 6. Template And New Apps

`apps/_template` is the reference implementation; `node scripts/new_poc.mjs <slug>` copies it, so every generated app starts compliant:

- `frontend/src/index.css`: only `@import "@internal/design-tokens/base.css";` plus `@tailwind` directives. No `@fontsource/*` dependency in `frontend/package.json`.
- `frontend/index.html`: anti-flash script (dark unless `light` was saved) and `<meta name="color-scheme" content="dark light">`. The desktop startup page (`--desktop`) has the same meta.
- Pages: `Home`, `Data`, `Settings` start with `PageHeader`; `Data` uses `KpiCard`, `Skeleton` (with a `role="status"` label) and `Alert`; the `llm` profile Settings page uses `CollapsibleSection` (collapsed once a key is configured), `FormField`, and offers the models returned by the connection test through a `datalist` while keeping free text.
- Dev-only gallery: `/design` (`routes/DesignGallery.tsx`) is registered only when `import.meta.env.DEV`; production builds exclude it.
- `tests/e2e/design-system.spec.ts`: 8 combinations (dark/light x FR/EN x 1366/760px). It asserts the theme class, that Inter, JetBrains Mono and Orbitron faces are loaded, and that `main` does not overflow horizontally; screenshots are attached to the report (no committed baselines because rendering differs per OS).
- The `llm` profile overlay (`apps/_template/profiles/llm`) replaces `App.tsx`, `routes/Settings.tsx` and the locales: any template change to these files must be mirrored there.

## 7. App Migration (October 2026)

All ten app frontends (catia-toolbox, corpus-agent, doc-reviewer, doc-writer, ecm-automation, flowchart-generator, image-processor, ocr-vision, pdf-toolkit, s1000d-extractor) were migrated mechanically, without visual redesign:

- Google Fonts `<link>`/`preconnect` tags removed from `index.html` (7 apps); `<meta name="color-scheme" content="dark light">` added where missing.
- `src/index.css` imports `@internal/design-tokens/base.css` instead of `theme.css`; app-level `@fontsource` imports and dependencies removed (flowchart-generator, image-processor, pdf-toolkit).
- Literal font names in app CSS and inline styles replaced by `var(--font-sans|mono|display)`; inline SVG text uses `style={{ fontFamily: "var(--font-mono)" }}` because CSS variables do not resolve in presentation attributes.
- `preview-skin.css` files no longer redefine `--shadow-card` (the themed token applies, so light mode gets its light shadow); their aliases (`--bg`, `--fg`, ...) are kept for compatibility.

Rules for app CSS from now on:

- Alias variables (`--bg: var(--color-bg-base)`) are tolerated in existing apps; new code uses Tailwind utilities or `var(--color-*)` directly.
- Never declare rules whose selector starts with a shared `.ui-*` class: the shell and primitives are styled by `@internal/ui` only. Element resets (`button { font: inherit }`) are acceptable.
- Recessed panels use `bg-2` / `surface.sunken`, cards use `card`, the page uses `bg`.

Each app owner should still review its screens in both themes; screens were not individually redesigned.

## 8. Guardrails

`bash scripts/check_standard.sh` enforces the design system (checks 18-22):

| Check | Fails when |
|---|---|
| 18 `theme.css genere depuis tokens.json` | `theme.css` was edited by hand or `tokens.json` changed without `pnpm tokens:build` |
| 19 `Pas de CDN de polices` | `fonts.googleapis.com` / `fonts.gstatic.com` appears in a frontend, `packages/` or `design-tokens/` |
| 20 `Polices via var(--font-*) uniquement` | `@fontsource` or a literal `Inter` / `Orbitron` / `JetBrains Mono` font declaration appears in app sources, `packages/ui/src`, or an app `package.json` |
| 21 `base.css + meta color-scheme` | a frontend `index.html` lacks `<meta name="color-scheme">` or its `src/index.css` does not import `@internal/design-tokens/base.css` |
| 22 `Pas de surcharge des classes .ui-*` | an app CSS rule selector starts with a shared `.ui-*` class |

Automated tests complete the guardrails:

| Command | Covers |
|---|---|
| `pnpm --filter @internal/design-tokens test` | theme.css sync, legacy variables, light/dark key parity, WCAG contrast of both palettes |
| `pnpm --filter @internal/ui test` | one Vitest per shared primitive |
| `pnpm --filter @apps/TEMPLATE-frontend test:e2e` | `/design` gallery in dark/light x FR/EN x 1366/760px, fonts loaded, no horizontal overflow |

Run them whenever `design-tokens/`, `packages/ui/` or `apps/_template/` change; they are cross-application changes that need explicit approval.
