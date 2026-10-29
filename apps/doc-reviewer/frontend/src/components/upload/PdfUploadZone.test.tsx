import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useDemoMode: vi.fn(),
}));

vi.mock("@internal/ui", () => ({
  useDemoMode: mocks.useDemoMode,
}));
vi.mock("../../lib/demoPdf", () => ({
  loadDemoPdf: vi.fn(),
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { PdfUploadZone } from "./PdfUploadZone";

describe("PdfUploadZone", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    mocks.useDemoMode.mockReturnValue({ mode: "normal", isReady: true });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  async function selectFiles(files: File[]) {
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    if (!input) throw new Error("Expected the dropzone file input.");
    Object.defineProperty(input, "files", { configurable: true, value: files });
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("keeps the existing single-file and document-format behavior by default", async () => {
    const file = new File(["pdf"], "manual.pdf", { type: "application/pdf" });
    const onFile = vi.fn();
    await act(async () => root.render(<PdfUploadZone onFile={onFile} />));
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');

    expect(input?.multiple).toBe(false);
    expect(input?.accept).toContain(".docx");
    await selectFiles([file]);

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("accepts multiple PDFs and calls the batch handler", async () => {
    const files = [
      new File(["first"], "first.pdf", { type: "application/pdf" }),
      new File(["second"], "second.pdf", { type: "application/pdf" }),
    ];
    const onFiles = vi.fn();
    await act(async () => {
      root.render(
        <PdfUploadZone
          multiple
          pdfOnly
          onFiles={onFiles}
          dropTitle="Drop PDFs here"
          inputLabel="PDF files"
        />,
      );
    });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');

    expect(input?.multiple).toBe(true);
    expect(input?.accept).toContain(".pdf");
    expect(input?.accept).not.toContain(".docx");
    expect(container.textContent).toContain("Drop PDFs here");
    await selectFiles(files);

    expect(onFiles).toHaveBeenCalledWith(files);
  });

  it("announces rejected files when a message is provided", async () => {
    const onFiles = vi.fn();
    await act(async () => {
      root.render(
        <PdfUploadZone
          multiple
          pdfOnly
          onFiles={onFiles}
          rejectedMessage="Select PDF files only."
        />,
      );
    });

    await selectFiles([new File(["text"], "notes.txt", { type: "text/plain" })]);

    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      "Select PDF files only.",
    );
    expect(onFiles).not.toHaveBeenCalled();
  });
});
