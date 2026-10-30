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
