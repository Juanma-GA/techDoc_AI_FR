// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getDocument: vi.fn() }));
vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: mocks.getDocument,
}));

import { checkReadablePdf } from "./checkReadablePdf";

const messages = {
  unreadablePdf: "Unreadable PDF",
  noTextLayer: "No text layer",
};

function createFile(): File {
  const file = new File(["%PDF-synthetic"], "sample.pdf", { type: "application/pdf" });
  Object.defineProperty(file, "arrayBuffer", {
    value: () => Promise.resolve(new Uint8Array([37, 80, 68, 70]).buffer),
  });
  return file;
}

function createDocument(pageTexts: string[][]) {
  const pages = pageTexts.map((strings) => ({
    getTextContent: vi.fn().mockResolvedValue({
      items: strings.map((str) => ({ str })),
    }),
    cleanup: vi.fn(),
  }));
  return {
    numPages: pages.length,
    getPage: vi.fn(async (pageNumber: number) => pages[pageNumber - 1]),
    destroy: vi.fn().mockResolvedValue(undefined),
    pages,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe("checkReadablePdf", () => {
  it("accepts a document with text on any page and checks each page", async () => {
    const document = createDocument([["  "], ["Readable content"]]);
    mocks.getDocument.mockReturnValue({ promise: Promise.resolve(document) });

    await expect(checkReadablePdf(createFile(), messages)).resolves.toBeUndefined();

    expect(document.getPage).toHaveBeenCalledTimes(2);
    expect(document.pages[0]?.cleanup).toHaveBeenCalledOnce();
    expect(document.pages[1]?.cleanup).toHaveBeenCalledOnce();
    expect(document.destroy).toHaveBeenCalledOnce();
  });

  it("rejects a document with no extractable text", async () => {
    const document = createDocument([[], [" \n\t "]]);
    mocks.getDocument.mockReturnValue({ promise: Promise.resolve(document) });

    await expect(checkReadablePdf(createFile(), messages)).rejects.toThrow(messages.noTextLayer);
    expect(document.destroy).toHaveBeenCalledOnce();
  });

  it("maps PDF.js parsing failures to an unreadable PDF error", async () => {
    const destroy = vi.fn().mockResolvedValue(undefined);
    mocks.getDocument.mockReturnValue({
      promise: Promise.reject(new Error("Malformed PDF")),
      destroy,
    });

    await expect(checkReadablePdf(createFile(), messages)).rejects.toThrow(messages.unreadablePdf);
    expect(destroy).toHaveBeenCalledOnce();
  });
});
