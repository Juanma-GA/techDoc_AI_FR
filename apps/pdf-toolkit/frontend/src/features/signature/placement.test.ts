import { describe, expect, it } from "vitest";

import {
  clampSignaturePlacement,
  clampTextPlacement,
  resizeSignaturePlacement,
  resizeTextPlacement,
  signatureHeight,
} from "./placement";

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

  it("keeps independently placed text boxes inside the page", () => {
    expect(clampTextPlacement({ x: 0.9, y: 0.95, fontSize: 14 }, 0.3, 0.1)).toEqual({
      x: 0.7,
      y: 0.9,
      fontSize: 14,
    });
  });

  it("resizes the signature proportionally from any corner", () => {
    const pageAspect = 612 / 792;
    const imageAspect = 3.2;
    const resized = resizeSignaturePlacement(
      { x: 0.2, y: 0.3, width: 0.2 },
      0.3,
      "topLeft",
      pageAspect,
      imageAspect,
    );

    expect(resized.width).toBe(0.3);
    expect(resized.x).toBeCloseTo(0.1);
    expect(resized.y + signatureHeight(resized, pageAspect, imageAspect)).toBeCloseTo(
      0.3 + signatureHeight({ x: 0, y: 0, width: 0.2 }, pageAspect, imageAspect),
    );
  });

  it("resizes text font size while anchoring the opposite corner", () => {
    const resized = resizeTextPlacement(
      { x: 0.2, y: 0.3, fontSize: 14 },
      28,
      "topLeft",
      0.2,
      0.05,
    );
    expect(resized.x).toBe(0);
    expect(resized.y).toBeCloseTo(0.25);
    expect(resized.fontSize).toBe(28);
  });

  it("keeps resized PDF font sizes as whole points", () => {
    const resized = resizeTextPlacement(
      { x: 0.2, y: 0.3, fontSize: 14 },
      13.6,
      "bottomRight",
      0.2,
      0.05,
    );
    expect(resized.fontSize).toBe(14);
  });
});
