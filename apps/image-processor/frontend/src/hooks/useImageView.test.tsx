import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useImageView } from "./useImageView";

function ImageViewHarness() {
  const editor = useImageView(false);
  return (
    <>
      <div ref={editor.previewRef} data-testid="preview">{editor.zoom}</div>
      <div data-testid="outside" />
    </>
  );
}

afterEach(cleanup);

describe("image view wheel zoom", () => {
  it("blocks page scrolling over the preview, including at zoom limits", () => {
    render(<ImageViewHarness />);
    const preview = screen.getByTestId("preview");

    const atMinimum = new WheelEvent("wheel", { deltaY: 1, bubbles: true, cancelable: true });
    fireEvent(preview, atMinimum);
    expect(atMinimum.defaultPrevented).toBe(true);
    expect(preview).toHaveTextContent("1");

    for (let step = 0; step < 12; step += 1) {
      fireEvent(
        preview,
        new WheelEvent("wheel", { deltaY: -1, bubbles: true, cancelable: true }),
      );
    }
    expect(preview).toHaveTextContent("4");

    const atMaximum = new WheelEvent("wheel", { deltaY: -1, bubbles: true, cancelable: true });
    fireEvent(preview, atMaximum);
    expect(atMaximum.defaultPrevented).toBe(true);
    expect(preview).toHaveTextContent("4");
  });

  it("leaves wheel scrolling outside the preview untouched", () => {
    render(<ImageViewHarness />);
    const outside = screen.getByTestId("outside");
    const wheelEvent = new WheelEvent("wheel", { deltaY: 1, bubbles: true, cancelable: true });

    fireEvent(outside, wheelEvent);

    expect(wheelEvent.defaultPrevented).toBe(false);
  });
});
