// @vitest-environment jsdom
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const pdfjsMocks = vi.hoisted(() => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: vi.fn(),
}));

vi.mock("pdfjs-dist", () => pdfjsMocks);

import i18n from "../../i18n";
import { RotationPreview } from "./RotationPreview";

beforeEach(async () => {
  await i18n.changeLanguage("en");
  pdfjsMocks.getDocument.mockReset();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RotationPreview", () => {
  it("renders the selected page at the current rotation and rerenders on angle changes", async () => {
    const renderOptions: Array<{ viewport: { rotation: number } }> = [];
    const page = {
      rotate: 0,
      getViewport: vi.fn(({ scale, rotation }: { scale: number; rotation: number }) => ({
        width: 400 * scale,
        height: 600 * scale,
        rotation,
      })),
      render: vi.fn((options: { viewport: { rotation: number } }) => {
        renderOptions.push(options);
        return { promise: Promise.resolve(), cancel: vi.fn() };
      }),
      cleanup: vi.fn(),
    };
    const pdfDocument = {
      numPages: 4,
      getPage: vi.fn().mockResolvedValue(page),
      destroy: vi.fn(),
    };
    pdfjsMocks.getDocument.mockReturnValue({
      promise: Promise.resolve(pdfDocument),
      destroy: vi.fn(),
    });
    const context = Object.create(null) as CanvasRenderingContext2D;
    Object.assign(context, { clearRect: vi.fn() });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context);
    const file = new File(["%PDF-synthetic"], "synthetic.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "arrayBuffer", {
      value: () => Promise.resolve(new ArrayBuffer(8)),
    });
    const view = render(<RotationPreview file={file} pageNumber={2} rotation={90} />);

    await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
    expect(pdfDocument.getPage).toHaveBeenCalledWith(2);
    expect(renderOptions[0]?.viewport.rotation).toBe(90);
    expect(view.getByLabelText(i18n.t("rotate.previewCanvasLabel", { page: 2, angle: 90 }))).toBeTruthy();

    view.rerender(<RotationPreview file={file} pageNumber={2} rotation={180} />);
    await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));
    expect(renderOptions[1]?.viewport.rotation).toBe(180);
  });
});
