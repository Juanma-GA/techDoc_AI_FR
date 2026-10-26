// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ResizeHandles, type ResizeCorner } from "./ResizeHandles";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

afterEach(cleanup);

describe("ResizeHandles", () => {
  it("renders four accessible corner controls and forwards pointer events", () => {
    const onResizeStart = vi.fn();
    const onResizeMove = vi.fn();
    const onResizeEnd = vi.fn();
    const onResizeKeyDown = vi.fn();
    const view = render(
      <ResizeHandles
        boxLabel="signature"
        disabled={false}
        onResizeStart={onResizeStart}
        onResizeMove={onResizeMove}
        onResizeEnd={onResizeEnd}
        onResizeKeyDown={onResizeKeyDown}
      />,
    );
    const corners: ResizeCorner[] = ["topLeft", "topRight", "bottomLeft", "bottomRight"];
    const buttons = corners.map((corner) =>
      view.getByRole("button", {
        name: i18n.t("signature.resizeHandle", {
          box: "signature",
          corner: i18n.t(`signature.corner.${corner}`),
        }),
      }),
    );

    expect(buttons).toHaveLength(4);
    fireEvent.pointerDown(buttons[3]!, { pointerId: 7, button: 0 });
    fireEvent.pointerMove(buttons[3]!, { pointerId: 7, clientX: 20, clientY: 20 });
    fireEvent.pointerUp(buttons[3]!, { pointerId: 7 });
    fireEvent.keyDown(buttons[3]!, { key: "ArrowRight" });

    expect(onResizeStart).toHaveBeenCalledWith("bottomRight", expect.anything());
    expect(onResizeMove).toHaveBeenCalled();
    expect(onResizeEnd).toHaveBeenCalled();
    expect(onResizeKeyDown).toHaveBeenCalledWith("bottomRight", expect.anything());
  });
});
