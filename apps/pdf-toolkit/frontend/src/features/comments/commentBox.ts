export type CommentBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CommentPoint = {
  x: number;
  y: number;
};

export const centeredCommentBox: CommentBox = {
  x: 0.4,
  y: 0.4,
  width: 0.2,
  height: 0.2,
};

export function commentBoxFromDrag(start: CommentPoint, end: CommentPoint): CommentBox {
  return clampCommentBox({
    x: Math.min(start.x, end.x),
    y: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y),
  });
}

export function clampCommentBox(box: CommentBox): CommentBox {
  const x = clamp(box.x, 0, 0.99);
  const y = clamp(box.y, 0, 0.99);
  return {
    x,
    y,
    width: clamp(box.width, 0.01, 1 - x),
    height: clamp(box.height, 0.01, 1 - y),
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, value));
}
