import type { OcrResultDto } from "./api";

export type LineBoxOffset = { lineIndex: number; x: number; y: number };

export function clampLineBoxOffset(
  box: number[][],
  x: number,
  y: number,
  width: number,
  height: number,
) {
  const minX = Math.min(...box.map(([pointX]) => pointX ?? 0));
  const maxX = Math.max(...box.map(([pointX]) => pointX ?? 0));
  const minY = Math.min(...box.map(([, pointY]) => pointY ?? 0));
  const maxY = Math.max(...box.map(([, pointY]) => pointY ?? 0));
  return {
    x: Math.max(-minX, Math.min(width - maxX, x)),
    y: Math.max(-minY, Math.min(height - maxY, y)),
  };
}

export function withLineBoxOffsets(
  result: OcrResultDto,
  offsets: LineBoxOffset[],
): OcrResultDto {
  const requestedOffsets = new Map(
    offsets.map(({ lineIndex, x, y }) => [lineIndex, { x, y }]),
  );
  return {
    ...result,
    lines: result.lines.map((line, lineIndex) => {
      const requested = requestedOffsets.get(lineIndex);
      if (!requested) return line;

      const originalBox = line.original_box ?? line.box;
      const bounded = clampLineBoxOffset(
        originalBox,
        requested.x,
        requested.y,
        result.width,
        result.height,
      );
      return {
        ...line,
        original_box: originalBox,
        box_offset_x: bounded.x,
        box_offset_y: bounded.y,
        box: originalBox.map(([x, y]) => [(x ?? 0) + bounded.x, (y ?? 0) + bounded.y]),
      };
    }),
  };
}
