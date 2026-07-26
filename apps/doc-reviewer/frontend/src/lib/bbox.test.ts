import { describe, expect, it } from "vitest";

import { bboxToCssRect, type ViewportLike } from "./bbox";

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
