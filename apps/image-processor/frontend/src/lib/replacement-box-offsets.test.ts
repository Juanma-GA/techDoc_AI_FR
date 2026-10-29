import { describe, expect, it } from "vitest";

import type { OcrResultDto } from "./api";
import { withLineBoxOffsets } from "./replacement-box-offsets";

const result: OcrResultDto = {
  width: 2480,
  height: 3508,
  source_width: 2480,
  source_height: 3508,
  full_text: "R-1",
  lines: [{
    text: "R-1",
    confidence: 1,
    box: [[100, 100], [200, 100], [200, 130], [100, 130]],
    matched_references: ["R-1"],
  }],
  references: [],
  edited_image: "data:image/jpeg;base64,AA==",
  filename: "source.jpg",
};

describe("replacement box offsets", () => {
  it("shifts both axes relative to the OCR box and clamps to the page", () => {
    const shifted = withLineBoxOffsets(result, [{ lineIndex: 0, x: 8, y: -4 }]);
    expect(shifted.lines[0]?.box).toEqual([
      [108, 96], [208, 96], [208, 126], [108, 126],
    ]);
    expect(shifted.lines[0]?.original_box).toEqual(result.lines[0]?.box);

    const clamped = withLineBoxOffsets(shifted, [{ lineIndex: 0, x: 5000, y: 5000 }]);
    expect(clamped.lines[0]?.box).toEqual([
      [2380, 3478], [2480, 3478], [2480, 3508], [2380, 3508],
    ]);
  });
});
