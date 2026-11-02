import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  flattenColors,
  hexToChannels,
  readTokens,
  renderThemeCss,
  themePath,
} from "../scripts/build-theme.mjs";

const tokens = readTokens();

test("theme.css is generated from tokens.json", () => {
  const current = readFileSync(themePath, "utf8").replace(/\r\n/g, "\n");
  assert.equal(current, renderThemeCss(tokens), "run `pnpm tokens:build`");
});

test("light overrides only use keys that exist in the dark palette", () => {
  const dark = new Set(flattenColors(tokens.color).map(([name]) => name));
  for (const [name] of flattenColors(tokens.themes.light.color)) {
    assert.ok(dark.has(name), `themes.light.color.${name} has no dark counterpart`);
  }
  for (const name of Object.keys(tokens.themes.light.shadow ?? {})) {
    assert.ok(name in tokens.shadow, `themes.light.shadow.${name} has no dark counterpart`);
  }
});

test("every legacy CSS variable is still emitted for both themes", () => {
  const css = renderThemeCss(tokens);
  const legacy = [
    "bg-base", "bg-2", "bg-3", "card-base", "card-hover", "brand-blue", "brand-blue-light",
    "semantic-success", "semantic-warning", "semantic-danger", "semantic-info",
    "accent-teal", "accent-purple", "accent-orange", "accent-pink", "accent-yellow",
    "text-base", "text-dim", "text-muted", "border-base", "border-md", "border-bright",
  ];
  for (const block of css.split(/\n(?=\.dark \{)/)) {
    for (const name of legacy) assert.match(block, new RegExp(`--color-${name}:`), name);
  }
});

test("hex colors expose rgb channels for Tailwind alpha modifiers", () => {
  assert.equal(hexToChannels("#2563eb"), "37 99 235");
  assert.equal(hexToChannels("#fff"), "255 255 255");
  assert.equal(hexToChannels("rgba(0,0,0,0.1)"), null);
  assert.match(renderThemeCss(tokens), /--color-semantic-success-rgb: \d+ \d+ \d+;/);
});
