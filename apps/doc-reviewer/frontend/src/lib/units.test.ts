import { describe, expect, it } from "vitest";

import { convert } from "./units";

describe("convert", () => {
  it("converts inch to cm", () => {
    expect(convert(12, "in", "metric")).toBe("30.48 cm");
  });

  it("converts feet to metres", () => {
    expect(convert(5, "ft", "metric")).toBe("1.52 m");
  });

  it("converts cm to inches", () => {
    const out = convert(2.54, "cm", "imperial");
    expect(out).toBe("1 in");
  });

  it("returns null for unknown pair", () => {
    expect(convert(10, "xyz", "imperial")).toBeNull();
  });
});
