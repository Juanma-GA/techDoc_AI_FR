import { describe, expect, it } from "vitest";

import { resolveInsertAfter, resolveSourcePages } from "./insertModel";

describe("resolveSourcePages", () => {
  it("selects every source page when the selection is empty", () => {
    expect(resolveSourcePages("  ", 3)).toEqual([1, 2, 3]);
  });

  it("keeps the typed order", () => {
    expect(resolveSourcePages("5,1-3", 5)).toEqual([5, 1, 2, 3]);
  });

  it.each(["6", "2,2", "3-1", "a", "1,,2"])("rejects %s", (selection) => {
    expect(resolveSourcePages(selection, 5)).toBeNull();
  });

  it("rejects an unread source", () => {
    expect(resolveSourcePages("", 0)).toBeNull();
  });
});

describe("resolveInsertAfter", () => {
  it("maps start and end to the target bounds", () => {
    expect(resolveInsertAfter("start", "", 4)).toBe(0);
    expect(resolveInsertAfter("end", "", 4)).toBe(4);
  });

  it("accepts a page inside the target", () => {
    expect(resolveInsertAfter("after", " 2 ", 4)).toBe(2);
    expect(resolveInsertAfter("after", "4", 4)).toBe(4);
  });

  it.each(["0", "5", "", "1.5", "-1"])("rejects after page %s", (page) => {
    expect(resolveInsertAfter("after", page, 4)).toBeNull();
  });

  it("rejects an unread target", () => {
    expect(resolveInsertAfter("start", "", 0)).toBeNull();
  });
});
