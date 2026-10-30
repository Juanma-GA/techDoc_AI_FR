import assert from "node:assert/strict";
import test from "node:test";

import { readTokens, themePalette } from "../scripts/build-theme.mjs";

// WCAG 2.x relative luminance / contrast ratio, with alpha compositing for rgba tokens.
function parse(value) {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) {
    const n = Number.parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgba = /^rgba?\(([^)]+)\)$/i.exec(value);
  if (!rgba) throw new Error(`Unsupported color: ${value}`);
  const [r, g, b, a = 1] = rgba[1].split(",").map((part) => Number.parseFloat(part));
  return [r, g, b, a];
}

function over(fg, bg) {
  const [r, g, b, a] = parse(fg);
  const [br, bgG, bb] = parse(bg);
  return [r * a + br * (1 - a), g * a + bgG * (1 - a), b * a + bb * (1 - a)];
}

function luminance([r, g, b]) {
  const lin = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(fg, bg, backdrop) {
  const surface = backdrop ? over(bg, backdrop) : over(bg, "#ffffff");
  const toHex = (rgb) => `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")}`;
  const text = over(fg, toHex(surface));
  const [l1, l2] = [luminance(text), luminance(surface)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

const get = (palette, path) => path.split(".").reduce((node, key) => node[key], palette.color);

// [foreground, background, minimum ratio, optional opaque backdrop for translucent backgrounds]
const PAIRS = [
  ["text.base", "bg.base", 7],
  ["text.base", "card.base", 7],
  ["text.dim", "bg.base", 4.5],
  ["text.dim", "bg.2", 4.5],
  ["text.dim", "card.base", 4.5],
  ["text.muted", "bg.base", 3],
  ["text.muted", "card.base", 3],
  ["brand.fg", "brand.blue", 4.5],
  ["brand.fg", "brand.hover", 3],
  ["brand.fg", "semantic.danger", 3],
  ["brand.text", "bg.2", 4.5],
  ["brand.text", "card.base", 4.5],
  ["nav.active-fg", "nav.active-bg", 4.5, "bg.2"],
  ["semantic.success", "card.base", 3],
  ["semantic.warning", "card.base", 3],
  ["semantic.danger", "card.base", 3],
  ["semantic.info", "card.base", 3],
];

// Light theme text meets WCAG AA for status colors too (they are used as text in badges).
const LIGHT_ONLY = [
  ["semantic.success", "card.base", 4.5],
  ["semantic.warning", "card.base", 4.5],
  ["semantic.danger", "card.base", 4.5],
  ["semantic.info", "card.base", 4.5],
];

const tokens = readTokens();

for (const theme of ["dark", "light"]) {
  const palette = themePalette(tokens, theme);
  const pairs = theme === "light" ? [...PAIRS, ...LIGHT_ONLY] : PAIRS;
  test(`${theme} palette meets contrast targets`, () => {
    const failures = pairs.flatMap(([fg, bg, min, backdrop]) => {
      const ratio = contrast(get(palette, fg), get(palette, bg), backdrop && get(palette, backdrop));
      return ratio >= min ? [] : [`${fg} on ${bg}: ${ratio.toFixed(2)} < ${min}`];
    });
    assert.deepEqual(failures, []);
  });
}

test("light cards stand out from the light app background", () => {
  const light = themePalette(tokens, "light");
  assert.notEqual(light.color.bg.base, light.color.card.base);
  assert.notEqual(light.shadow.card, tokens.shadow.card, "light theme needs its own shadow");
});
