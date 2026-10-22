// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { SignaturePad } from "./SignaturePad";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SignaturePad", () => {
  it("saves a drawn signature as a temporary PNG file", () => {
    const context = Object.create(null) as CanvasRenderingContext2D;
    Object.assign(context, {
      beginPath: vi.fn(),
      clearRect: vi.fn(),
      lineTo: vi.fn(),
      moveTo: vi.fn(),
      stroke: vi.fn(),
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback, type) => {
      callback(new Blob(["synthetic signature"], { type }));
    });
    const onSave = vi.fn();
    const onClear = vi.fn();
    const view = render(
      <SignaturePad disabled={false} onSave={onSave} onClear={onClear} />,
    );
    const canvas = view.getByLabelText(i18n.t("signature.canvasLabel"));

    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 8, clientY: 8 });
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 40, clientY: 25 });
    fireEvent.pointerUp(canvas, { pointerId: 1 });
    fireEvent.click(view.getByRole("button", { name: i18n.t("signature.save") }));

    expect(context.stroke).toHaveBeenCalled();
    expect(onSave).toHaveBeenCalledTimes(1);
    const savedFile = onSave.mock.calls[0]?.[0];
    expect(savedFile).toBeInstanceOf(File);
    expect(savedFile?.type).toBe("image/png");
    expect(savedFile?.name).toBe("signature.png");
    expect(onClear).not.toHaveBeenCalled();
  });
});
