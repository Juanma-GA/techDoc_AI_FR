import { describe, expect, it } from "vitest";

import { bboxToCssRect, bboxToPercentRect, type ViewportLike } from "./bbox";

function viewportFor(scale: number): ViewportLike {
  return {
    convertToViewportRectangle([x0, y0, x1, y1]) {
      return [x0 * scale, y0 * scale, x1 * scale, y1 * scale];
    },
  };
}

describe("bboxToCssRect", () => {
  it("scales bbox at 1x without dpr", () => {
    const rect = bboxToCssRect({ x0: 10, y0: 20, x1: 50, y1: 40 }, viewportFor(1), 1);
    expect(rect).toEqual({ left: 10, top: 20, width: 40, height: 20 });
  });

  it("scales at 2x and divides by dpr=2 to give CSS pixels", () => {
    const rect = bboxToCssRect({ x0: 10, y0: 20, x1: 50, y1: 40 }, viewportFor(2), 2);
    expect(rect).toEqual({ left: 10, top: 20, width: 40, height: 20 });
  });

  it("normalises swapped corners", () => {
    const rect = bboxToCssRect({ x0: 50, y0: 40, x1: 10, y1: 20 }, viewportFor(1), 1);
    expect(rect).toEqual({ left: 10, top: 20, width: 40, height: 20 });
  });
});

describe("bboxToPercentRect", () => {
  it("keeps the historical PDF-point to page-percent mapping", () => {
    const rect = bboxToPercentRect({
      x0: 100,
      y0: 50,
      x1: 200,
      y1: 100,
      page_w: 600,
      page_h: 400,
      page_rotation: 0,
    });

    expect(rect?.left).toBeCloseTo(100 / 6);
    expect(rect?.top).toBeCloseTo(12.5);
    expect(rect?.width).toBeCloseTo(100 / 6);
    expect(rect?.height).toBeCloseTo(12.5);
  });

  it.each([
    [90, { left: 594 / 800 * 100, top: 100 / 600 * 100, width: 27.5 / 800 * 100, height: 81.12 / 600 * 100 }],
    [180, { left: 418.88 / 600 * 100, top: 594 / 800 * 100, width: 81.12 / 600 * 100, height: 27.48 / 800 * 100 }],
    [270, { left: 178.5 / 800 * 100, top: 418.88 / 600 * 100, width: 27.48 / 800 * 100, height: 81.12 / 600 * 100 }],
  ])("maps a PDF bbox into the %s-degree displayed page", (rotation, expected) => {
    const rect = bboxToPercentRect({
      x0: 100,
      y0: 178.5,
      x1: 181.12,
      y1: 205.98,
      page_w: rotation === 90 || rotation === 270 ? 800 : 600,
      page_h: rotation === 90 || rotation === 270 ? 600 : 800,
      page_rotation: rotation,
    });

    expect(rect?.left).toBeCloseTo(expected.left);
    expect(rect?.top).toBeCloseTo(expected.top);
    expect(rect?.width).toBeCloseTo(expected.width);
    expect(rect?.height).toBeCloseTo(expected.height);
  });
});
