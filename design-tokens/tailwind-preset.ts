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
 *
 * Theming :
 *   - All color tokens are emitted as CSS custom properties and consumed
 *     by Tailwind classes via `var(--color-*)`. The actual values for
 *     each theme (dark/light) live in `theme.css`. To enable theming in
 *     an app, import `@internal/design-tokens/theme.css` from `index.css`.
 *   - Non-color tokens (font, radius, shadow, layout) are not theme-
 *     dependent, so they are read directly from `tokens.json`.
 */

import type { Config } from "tailwindcss";

import tokens from "./tokens.json";

const cssVar = (name: string) => `var(--color-${name})`;

const preset = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: cssVar("bg-base"),
          2: cssVar("bg-2"),
          3: cssVar("bg-3"),
        },
        card: {
          DEFAULT: cssVar("card-base"),
          hover: cssVar("card-hover"),
        },
        brand: {
          DEFAULT: cssVar("brand-blue"),
          blue: cssVar("brand-blue"),
          "blue-light": cssVar("brand-blue-light"),
        },
        success: cssVar("semantic-success"),
        warning: cssVar("semantic-warning"),
        danger: cssVar("semantic-danger"),
        info: cssVar("semantic-info"),
        accent: {
          teal: cssVar("accent-teal"),
          purple: cssVar("accent-purple"),
          orange: cssVar("accent-orange"),
          pink: cssVar("accent-pink"),
          yellow: cssVar("accent-yellow"),
        },
        fg: {
          DEFAULT: cssVar("text-base"),
          dim: cssVar("text-dim"),
          muted: cssVar("text-muted"),
        },
      },
      borderColor: {
        DEFAULT: cssVar("border-base"),
        md: cssVar("border-md"),
        bright: cssVar("border-bright"),
      },
      ringColor: {
        DEFAULT: cssVar("brand-blue-light"),
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
      },
      borderRadius: {
        sm: tokens.radius.sm,
        lg: tokens.radius.lg,
      },
      boxShadow: {
        card: tokens.shadow.card,
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
