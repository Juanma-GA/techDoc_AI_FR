import { describe, expect, it, vi } from "vitest";
import type { PDFDocumentProxy } from "pdfjs-dist";

import { bookmarkGroups, readSplitBookmarks, type SplitBookmark } from "./bookmarkSplit";
import { parsePageSelection, uniqueFileNames } from "./splitModel";

function node(title: string, dest: string | unknown[] | null) {
  return {
    title, dest, items: [], bold: false, italic: false, color: new Uint8ClampedArray(3),
    url: null, unsafeUrl: undefined, newWindow: undefined, count: undefined,
  };
}

function document(outline: Awaited<ReturnType<PDFDocumentProxy["getOutline"]>> | null) {
  return {
    numPages: 12,
    getOutline: vi.fn().mockResolvedValue(outline),
    getDestination: vi.fn().mockResolvedValue([{ num: 25, gen: 0 }]),
    getPageIndex: vi.fn().mockResolvedValue(7),
  };
}

describe("reading split bookmarks", () => {
  it("resolves numeric, named and reference destinations and preserves levels", async () => {
    const parent = { ...node("Chapter", [2]), items: [node("Section", "section")] };
    const pdf = document([parent, node("End", [{ num: 44, gen: 0 }])]);
    const result = await readSplitBookmarks(pdf);
    expect(result).toEqual({
      bookmarks: [
        { title: "Chapter", page: 3, level: 1 },
        { title: "Section", page: 8, level: 2 },
        { title: "End", page: 8, level: 1 },
      ],
      skipped: 0,
    });
    expect(pdf.getDestination).toHaveBeenCalledWith("section");
    expect(pdf.getPageIndex).toHaveBeenCalledWith({ num: 25, gen: 0 });
  });

  it("handles absent outlines and reports unusable destinations", async () => {
    expect(await readSplitBookmarks(document(null))).toEqual({ bookmarks: [], skipped: 0 });
    const pdf = document([
      node("External", null), node("Missing", "missing"), node("Negative", [-1]),
      node("Out of range", [12]), node("Fraction", [1.5]), node("Malformed", [{}]),
      { ...node("Parent without destination", null), items: [node("Child", [0])] },
    ]);
    pdf.getDestination.mockResolvedValue(null);
    expect(await readSplitBookmarks(pdf)).toEqual({
      bookmarks: [{ title: "Child", page: 1, level: 2 }], skipped: 7,
    });
  });

  it("propagates read failures rather than silently exporting a partial outline", async () => {
    const pdf = document([node("Valid", [0]), node("Broken", [{ num: 4, gen: 0 }])]);
    pdf.getPageIndex.mockRejectedValue(new Error("Broken reference"));
    await expect(readSplitBookmarks(pdf)).rejects.toThrow("Broken reference");
  });
});

describe("bookmark groups", () => {
  const bookmarks: SplitBookmark[] = [
    { title: "End", page: 8, level: 1 },
    { title: "Chapter", page: 3, level: 1 },
    { title: "Duplicate page", page: 3, level: 1 },
    { title: "Section", page: 5, level: 2 },
  ];

  it("sorts boundaries, merges duplicate pages and keeps every page exactly once", () => {
    const groups = bookmarkGroups(bookmarks, 1, 10);
    expect(groups).toEqual([
      { title: "", pages: "1-2" },
      { title: "Chapter", pages: "3-7" },
      { title: "End", pages: "8-10" },
    ]);
    expect(groups.flatMap((group) => parsePageSelection(group.pages, 10))).toEqual(
      Array.from({ length: 10 }, (_, index) => index + 1),
    );
    expect(bookmarks[0]?.page).toBe(8);
  });

  it("uses only the selected level and supports a last-page bookmark", () => {
    expect(bookmarkGroups(bookmarks, 2, 10)).toEqual([
      { title: "", pages: "1-4" }, { title: "Section", pages: "5-10" },
    ]);
    expect(bookmarkGroups([{ title: "Last", page: 10, level: 1 }], 1, 10)).toEqual([
      { title: "", pages: "1-9" }, { title: "Last", pages: "10" },
    ]);
    expect(bookmarkGroups([], 1, 10)).toEqual([]);
    expect(bookmarkGroups(bookmarks, 3, 10)).toEqual([]);
    expect(bookmarkGroups([{ title: "Only", page: 1, level: 1 }], 1, 1)).toEqual([
      { title: "Only", pages: "1" },
    ]);
  });

  it("uses existing name sanitization for bookmark titles", () => {
    expect(uniqueFileNames(["A/B", "A:B", "CON", ""])).toEqual([
      "A_B.pdf", "A_B_2.pdf", "_CON.pdf", "document-4.pdf",
    ]);
  });
});
