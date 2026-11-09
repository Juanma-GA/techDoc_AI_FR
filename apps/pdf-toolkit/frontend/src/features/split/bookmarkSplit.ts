import type { PDFDocumentProxy } from "pdfjs-dist";

export type SplitBookmark = { title: string; page: number; level: number };
type OutlineNode = { title: string; dest: string | unknown[] | null; items: OutlineNode[] };
type BookmarkDocument = Pick<PDFDocumentProxy, "getOutline" | "getDestination" | "getPageIndex" | "numPages">;

export async function readSplitBookmarks(document: BookmarkDocument) {
  const bookmarks: SplitBookmark[] = [];
  let skipped = 0;
  const outline: OutlineNode[] | null = await document.getOutline();
  const pending = (outline ?? []).map((node) => ({ node, level: 1 })).reverse();
  while (pending.length > 0) {
    const entry = pending.pop();
    if (!entry) break;
    const { node, level } = entry;
    for (let index = node.items.length - 1; index >= 0; index -= 1) {
      const child = node.items[index];
      if (child) pending.push({ node: child, level: level + 1 });
    }
    const destination: unknown = typeof node.dest === "string"
      ? await document.getDestination(node.dest)
      : node.dest;
    const target: unknown = Array.isArray(destination) ? destination[0] : null;
    let page = 0;
    if (typeof target === "number" && Number.isInteger(target)) {
      page = target + 1;
    } else if (
      typeof target === "object" && target !== null &&
      "num" in target && "gen" in target &&
      typeof target.num === "number" && Number.isInteger(target.num) &&
      typeof target.gen === "number" && Number.isInteger(target.gen)
    ) {
      page = await document.getPageIndex({ num: target.num, gen: target.gen }) + 1;
    }
    if (page >= 1 && page <= document.numPages) {
      bookmarks.push({ title: node.title, page, level });
    } else {
      skipped += 1;
    }
  }
  return { bookmarks, skipped };
}

export function bookmarkGroups(bookmarks: SplitBookmark[], level: number, pageCount: number) {
  const seen = new Set<number>();
  const starts = bookmarks
    .filter((bookmark) => bookmark.level === level && bookmark.page >= 1 && bookmark.page <= pageCount)
    .sort((left, right) => left.page - right.page)
    .filter((bookmark) => {
      if (seen.has(bookmark.page)) return false;
      seen.add(bookmark.page);
      return true;
    });
  if (starts.length === 0) return [];
  if ((starts[0]?.page ?? 1) > 1) starts.unshift({ title: "", page: 1, level });
  return starts.map((bookmark, index) => {
    const last = (starts[index + 1]?.page ?? pageCount + 1) - 1;
    return {
      pages: bookmark.page === last ? `${last}` : `${bookmark.page}-${last}`,
      title: bookmark.title,
    };
  });
}
