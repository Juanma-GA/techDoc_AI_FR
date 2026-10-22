import { describe, expect, it } from "vitest";

import { clampSignaturePlacement, signatureHeight } from "./placement";

describe("signature placement", () => {
  it("keeps the signature inside the page while preserving its aspect ratio", () => {
    const aspect = 612 / 792;
    const imageAspect = 3.2;
    const placement = clampSignaturePlacement(
      { x: 0.9, y: 0.99, width: 0.4 },
      aspect,
      imageAspect,
    );

    expect(placement.x).toBeCloseTo(0.6);
    expect(placement.y + signatureHeight(placement, aspect, imageAspect)).toBeCloseTo(1);
    expect(placement.width).toBe(0.4);
  });

  it("uses safe bounds when page or image dimensions are invalid", () => {
    expect(clampSignaturePlacement({ x: -1, y: 2, width: 0.4 }, Number.NaN, 0).x).toBe(0);
  });
});
