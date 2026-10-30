/**
 * Tailwind preset — Midnight Executive (dual-theme).
 *
 * Imported by every app/package that uses Tailwind:
 *
 *     import preset from "@internal/design-tokens/tailwind-preset";
 *     export default { presets: [preset], content: [...], ... } satisfies Config;
 *
 * Naming notes:
 *   - `text.*` from tokens.json is exposed under Tailwind as `fg.*` to
 *     avoid the awkward `text-text-dim` utility name. Use `text-fg`,
 *     `text-fg-dim`, `text-fg-muted`.
 *   - `border.*` is mapped to Tailwind's `borderColor` so `border` (no
 *     suffix) uses the default token. Variants: `border-md`, `border-bright`.
 *   - Text/icons on a brand or danger fill use `text-brand-fg` (never `text-fg`,
 *     which is dark in the light theme).
 *
 * Theming :
 *   - Color utilities read CSS custom properties generated in `theme.css`
 *     (`:root` = light, `.dark` = dark). Import it once per app through
 *     `@internal/design-tokens/base.css`.
 *   - Hex tokens are consumed as `rgb(var(--color-x-rgb) / <alpha-value>)`, so
 *     opacity modifiers (`bg-success/15`, `border-danger/40`) generate CSS.
 *     Tokens already defined with an alpha (borders, `brand.soft`, `overlay`)
 *     are consumed as plain `var(--color-x)` and do not accept modifiers.
 *   - Shadows are themed through `--shadow-*`; fonts, sizes, radius and motion
 *     are static and read from `tokens.json`.
 *   - Radius `md`/`xl` keep Tailwind defaults for backward compatibility; the
 *     tokenized radii are `rounded-xs`, `rounded-sm` and `rounded-lg`.
 */

import type { Config } from "tailwindcss";

import tokens from "./tokens.json";

type ColorTree = { [key: string]: string | ColorTree };

// Same flattening as scripts/build-theme.mjs: color.brand.blue-light -> "brand-blue-light".
function flatten(node: string | ColorTree, prefix = ""): Record<string, string> {
  if (typeof node === "string") return { [prefix]: node };
  return Object.entries(node).reduce<Record<string, string>>(
    (acc, [key, value]) => ({ ...acc, ...flatten(value, prefix ? `${prefix}-${key}` : key) }),
    {},
  );
}

const FLAT_COLORS = flatten(tokens.color as ColorTree);
const isHex = (value: string | undefined) => !!value && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(value);

/** Color utility value for `--color-<name>` (alpha-capable when the token is a hex color). */
export const tokenColor = (name: string) => {
  if (!(name in FLAT_COLORS)) throw new Error(`Unknown design token color: ${name}`);
  return isHex(FLAT_COLORS[name])
    ? `rgb(var(--color-${name}-rgb) / <alpha-value>)`
    : `var(--color-${name})`;
};

const preset = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: tokenColor("bg-base"),
          2: tokenColor("bg-2"),
          3: tokenColor("bg-3"),
        },
        card: {
          DEFAULT: tokenColor("card-base"),
          hover: tokenColor("card-hover"),
        },
        brand: {
          DEFAULT: tokenColor("brand-blue"),
          blue: tokenColor("brand-blue"),
          "blue-light": tokenColor("brand-blue-light"),
          fg: tokenColor("brand-fg"),
          hover: tokenColor("brand-hover"),
          text: tokenColor("brand-text"),
          soft: tokenColor("brand-soft"),
        },
        success: tokenColor("semantic-success"),
        warning: tokenColor("semantic-warning"),
        danger: tokenColor("semantic-danger"),
        info: tokenColor("semantic-info"),
        accent: {
          teal: tokenColor("accent-teal"),
          purple: tokenColor("accent-purple"),
          orange: tokenColor("accent-orange"),
          pink: tokenColor("accent-pink"),
          yellow: tokenColor("accent-yellow"),
        },
        fg: {
          DEFAULT: tokenColor("text-base"),
          dim: tokenColor("text-dim"),
          muted: tokenColor("text-muted"),
        },
        surface: {
          sunken: tokenColor("surface-sunken"),
        },
        focus: tokenColor("focus-ring"),
        overlay: tokenColor("overlay"),
      },
      borderColor: {
        DEFAULT: tokenColor("border-base"),
        md: tokenColor("border-md"),
        bright: tokenColor("border-bright"),
      },
      ringColor: {
        DEFAULT: tokenColor("focus-ring"),
      },
      fontFamily: {
        sans: tokens.font.sans,
        mono: tokens.font.mono,
        display: tokens.font.display,
      },
      fontSize: {
        base: [
          tokens.fontSize.base,
          { lineHeight: tokens.lineHeight.base },
        ],
        label: [
          tokens.fontSize.label,
          { lineHeight: "1.2", letterSpacing: "1px" },
        ],
        "card-title": [tokens.fontSize["card-title"], { lineHeight: "1.3" }],
        "page-title": [tokens.fontSize["page-title"], { lineHeight: "1.25" }],
      },
      borderRadius: {
        xs: tokens.radius.xs,
        sm: tokens.radius.sm,
        lg: tokens.radius.lg,
      },
      boxShadow: {
        card: "var(--shadow-card)",
        popover: "var(--shadow-popover)",
      },
      transitionDuration: {
        fast: tokens.motion["duration-fast"],
        base: tokens.motion["duration-base"],
      },
      transitionTimingFunction: {
        standard: tokens.motion["easing-standard"],
      },
      spacing: {
        "sidebar-w": tokens.layout["sidebar-w"],
        "topbar-h": tokens.layout["topbar-h"],
      },
      width: {
        "sidebar-w": tokens.layout["sidebar-w"],
      },
      height: {
        "topbar-h": tokens.layout["topbar-h"],
      },
    },
  },
} satisfies Partial<Config>;

export default preset;
