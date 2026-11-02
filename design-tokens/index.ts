/**
 * JS/TS direct access to design tokens.
 *
 * Use this when you need a token value in code (e.g. Recharts colors,
 * inline SVG fills, charting libraries that don't read CSS variables).
 *
 *     import { tokens, color, colorByTheme, currentTheme } from "@internal/design-tokens";
 *     <Bar fill={color.brand.blue} />                                // dark default
 *     <Bar fill={colorByTheme(currentTheme(), "brand.blue")} />      // theme-aware
 *
 * Backward compat: `color.*` returns the dark/default values flat. For
 * theme-aware code, use `colorByTheme(theme, path)` / `shadowByTheme`.
 * In markup and CSS, prefer Tailwind utilities or `var(--color-*)`.
 *
 * Never duplicate hex values in your code. The check_standard.sh
 * script will fail any commit that introduces a literal hex outside
 * of this folder.
 */

import tokensJson from "./tokens.json";

export const tokens = tokensJson;
export const color = tokensJson.color;
export const font = tokensJson.font;
export const fontSize = tokensJson.fontSize;
export const radius = tokensJson.radius;
export const shadow = tokensJson.shadow;
export const motion = tokensJson.motion;
export const layout = tokensJson.layout;

export type Theme = "dark" | "light";

export type DesignTokens = typeof tokensJson;

/** Current theme as applied on <html> by the anti-flash script / ThemeToggle. */
export function currentTheme(root: Element = document.documentElement): Theme {
  return root.classList.contains("dark") ? "dark" : "light";
}

/**
 * Resolve a shadow token (`"card"`, `"popover"`) for a given theme.
 * Prefer the `--shadow-*` CSS variables / `shadow-card` utility in markup.
 */
export function shadowByTheme(theme: Theme, name: keyof typeof tokensJson.shadow): string {
  if (theme === "dark") return tokensJson.shadow[name];
  const light = tokensJson.themes.light.shadow as Partial<typeof tokensJson.shadow>;
  return light[name] ?? tokensJson.shadow[name];
}

/**
 * Resolve a color path (`"brand.blue"`, `"text.base"`) for a given theme.
 * Falls back to the dark/default value if the light override is missing.
 */
export function colorByTheme(theme: Theme, path: string): string {
  const segments = path.split(".");
  const fromDark = walk(tokensJson.color as Record<string, unknown>, segments);
  if (theme === "dark") return fromDark;
  const fromLight = walk(
    (tokensJson.themes?.light?.color ?? {}) as Record<string, unknown>,
    segments,
  );
  return fromLight ?? fromDark;
}

function walk(node: Record<string, unknown>, segments: string[]): string {
  let current: unknown = node;
  for (const segment of segments) {
    if (typeof current !== "object" || current === null) return "";
    current = (current as Record<string, unknown>)[segment];
  }
  return typeof current === "string" ? current : "";
}
