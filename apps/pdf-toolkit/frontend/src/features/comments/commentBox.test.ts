import { describe, expect, it } from "vitest";

import { clampCommentBox, commentBoxFromDrag, centeredCommentBox } from "./commentBox";

describe("comment boxes", () => {
  it("creates a box when dragging in either direction", () => {
    const box = commentBoxFromDrag({ x: 0.8, y: 0.7 }, { x: 0.2, y: 0.1 });
    expect(box.x).toBe(0.2);
    expect(box.y).toBe(0.1);
    expect(box.width).toBeCloseTo(0.6);
    expect(box.height).toBeCloseTo(0.6);
  });

  it("keeps a minimum-size selection inside the page", () => {
    const minimumBox = commentBoxFromDrag({ x: 1, y: 1 }, { x: 1, y: 1 });
    expect(minimumBox.x).toBe(0.99);
    expect(minimumBox.y).toBe(0.99);
    expect(minimumBox.width).toBe(0.01);
    expect(minimumBox.height).toBe(0.01);

    const clampedBox = clampCommentBox({ x: 0.9, y: -1, width: 0.5, height: 2 });
    expect(clampedBox.x).toBe(0.9);
    expect(clampedBox.y).toBe(0);
    expect(clampedBox.width).toBeCloseTo(0.1);
    expect(clampedBox.height).toBe(1);
  });

  it("provides a centered box for keyboard users", () => {
    expect(centeredCommentBox.x + centeredCommentBox.width / 2).toBe(0.5);
    expect(centeredCommentBox.y + centeredCommentBox.height / 2).toBe(0.5);
  });
});
