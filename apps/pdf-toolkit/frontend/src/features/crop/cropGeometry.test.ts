import { describe, expect, it } from "vitest";

import { detectVisibleBounds, pdfCropRectFromRegion } from "./cropGeometry";

function pixelsWithContent(
  width: number,
  height: number,
  content: { left: number; top: number; right: number; bottom: number } | null,
): Uint8ClampedArray {
  const pixels = new Uint8ClampedArray(width * height * 4);
  pixels.fill(255);
  if (!content) return pixels;

  for (let y = content.top; y < content.bottom; y++) {
    for (let x = content.left; x < content.right; x++) {
      const offset = (y * width + x) * 4;
      pixels[offset] = 0;
      pixels[offset + 1] = 0;
      pixels[offset + 2] = 0;
      pixels[offset + 3] = 255;
    }
  }
  return pixels;
}

describe("detectVisibleBounds", () => {
  it("finds non-white page content and keeps a safety margin", () => {
    const region = detectVisibleBounds(
      pixelsWithContent(20, 20, { left: 8, top: 7, right: 12, bottom: 13 }),
      20,
      20,
    );

    expect(region).toEqual({ left: 0.25, top: 0.2, right: 0.75, bottom: 0.8 });
  });

  it("leaves blank pages unchanged", () => {
    expect(detectVisibleBounds(pixelsWithContent(12, 12, null), 12, 12)).toBeNull();
  });

  it("rejects invalid rendered pixel buffers", () => {
    expect(() => detectVisibleBounds(new Uint8ClampedArray(4), 2, 2)).toThrow(RangeError);
  });

  it("maps the top-left preview coordinates to ordered PDF coordinates", () => {
    const convertToPdfPoint = (x: number, y: number): [number, number] => [x, 200 - y];
    const crop = pdfCropRectFromRegion(
      1,
      {
        width: 100,
        height: 200,
        convertToPdfPoint,
      },
      { left: 0.1, top: 0.2, right: 0.8, bottom: 0.7 },
    );

    expect(crop).toEqual({ page: 1, x1: 10, y1: 60, x2: 80, y2: 160 });
  });
});
