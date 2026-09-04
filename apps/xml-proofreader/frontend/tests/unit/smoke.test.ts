import { describe, it, expect } from "vitest";
import { COLOR_RGB, rgbToColor } from "../../src/core/model/types";

describe("F0 scaffold smoke", () => {
  it("exposes Oxygen highlight color mapping", () => {
    expect(COLOR_RGB.yellow).toBe("255,243,163");
    expect(rgbToColor("255,243,163")).toBe("yellow");
    expect(rgbToColor("188,220,255")).toBe("blue");
  });
});
