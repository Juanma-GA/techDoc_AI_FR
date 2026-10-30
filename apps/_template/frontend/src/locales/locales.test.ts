import { describe, expect, it } from "vitest";

import en from "./en.json";
import fr from "./fr.json";

type Tree = { [key: string]: string | Tree };

function flatten(node: Tree, prefix = ""): Record<string, string> {
  return Object.entries(node).reduce<Record<string, string>>((acc, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === "string" ? { ...acc, [path]: value } : { ...acc, ...flatten(value, path) };
  }, {});
}

const FR = flatten(fr as Tree);
const EN = flatten(en as Tree);

describe("locales", () => {
  it("define the same keys in FR and EN", () => {
    expect(Object.keys(FR).sort()).toEqual(Object.keys(EN).sort());
  });

  it("keep their accents (no character replaced by '?' or U+FFFD)", () => {
    const corrupted = Object.entries({ ...FR, ...EN }).filter(([, value]) =>
      /[A-Za-z]\?[A-Za-z]|\? l'|\uFFFD|Ã©|Ã¨|â€/.test(value),
    );
    expect(corrupted).toEqual([]);
  });
});
