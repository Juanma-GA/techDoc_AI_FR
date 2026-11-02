import { describe, expect, it } from "vitest";

import {
  applyNamePattern,
  buildValuePattern,
  chunkRows,
  clampZone,
  extractValue,
  formatPageSelection,
  groupPageValues,
  maxSplitGroups,
  parsePageSelection,
  parseSplitRanges,
  parsePastedRows,
  sanitizeBaseName,
  uniqueFileNames,
} from "./splitModel";

const summarize = (rows: { pages: string; value: string }[]) =>
  rows.map((row) => `${row.pages}=${row.value}`);

describe("page selections", () => {
  it("parses one document per custom range and keeps combined selections", () => {
    expect(parseSplitRanges("1-4 ; 5-8\n9-12;13-16", 16)).toEqual(["1-4", "5-8", "9-12", "13-16"]);
    expect(parseSplitRanges("1-3,5;6-8", 8)).toEqual(["1-3,5", "6-8"]);
    const maximumRanges = Array.from({ length: maxSplitGroups }, (_, index) => `${index + 1}`).join(";");
    expect(parseSplitRanges(maximumRanges, maxSplitGroups)).toHaveLength(5000);
    expect(parseSplitRanges(`${maximumRanges};5001`, maxSplitGroups + 1)).toBeNull();
    expect(parseSplitRanges(" ; \n", 16)).toBeNull();
    expect(parseSplitRanges("1-4;15-18", 16)).toBeNull();
    expect(parseSplitRanges("4-1;5", 16)).toBeNull();
    expect(parseSplitRanges("1-4;abc", 16)).toBeNull();
  });

  it("parses ranges and rejects out-of-range pages", () => {
    expect(parsePageSelection("1-3, 5", 6)).toEqual([1, 2, 3, 5]);
    expect(parsePageSelection("4-2", 6)).toBeNull();
    expect(parsePageSelection("7", 6)).toBeNull();
    expect(parsePageSelection("", 6)).toBeNull();
  });

  it("formats sorted ranges", () => {
    expect(formatPageSelection([5, 1, 2, 3, 3, 8])).toBe("1-3,5,8");
  });

  it("chunks pages into regular rows", () => {
    expect(chunkRows(7, 3).map((row) => row.pages)).toEqual(["1-3", "4-6", "7"]);
  });
});

describe("pasted rows", () => {
  it("accepts semicolon, tab and pipe separators", () => {
    const { rows, rejected } = parsePastedRows("1-2;A\n3\tB\n\n4 | C\nfoo;D");
    expect(summarize(rows)).toEqual(["1-2=A", "3=B", "4=C"]);
    expect(rejected).toEqual([5]);
  });
});

describe("value extraction", () => {
  it("keeps the whole text for the text type", () => {
    expect(extractValue("  Ref  A320\n001 ", buildValuePattern("text", ""))).toBe("Ref A320 001");
  });

  it("extracts numbers and codes", () => {
    expect(extractValue("Page 12,5 total", buildValuePattern("number", ""))).toBe("12,5");
    expect(extractValue(" -A320-001/B. suite", buildValuePattern("code", ""))).toBe("A320-001/B");
  });

  it("uses the first capture group of a custom regex", () => {
    const pattern = buildValuePattern("regex", "N°\\s*(\\S+)");
    expect(extractValue("Dossier N° 4521-X", pattern)).toBe("4521-X");
    expect(extractValue("aucune", pattern)).toBe("");
    expect(() => buildValuePattern("regex", "(")).toThrow();
  });
});

describe("groupPageValues", () => {
  const values = ["", "A", "A", "", "B", "A"];

  it("starts a document on each change and attaches missing pages", () => {
    const result = groupPageValues(values, "change", "previous");
    expect(summarize(result.rows)).toEqual(["1-4=A", "5=B", "6=A"]);
    expect(result.missingPages).toEqual([1, 4]);
  });

  it("groups identical values and skips missing pages", () => {
    const result = groupPageValues(values, "same", "skip");
    expect(summarize(result.rows)).toEqual(["2-3,6=A", "5=B"]);
  });
});

describe("file names", () => {
  it("applies the pattern tokens", () => {
    const context = { value: "A1", index: 3, pages: "4-6", sourceName: "manuel", total: 12 };
    expect(applyNamePattern("{nom}_{valeur}_{n}_{pages}", context)).toBe("manuel_A1_03_4-6");
    expect(applyNamePattern("{NAME}-{Value}", context)).toBe("manuel-A1");
  });

  it("sanitizes and deduplicates names like the backend", () => {
    expect(sanitizeBaseName(" a/b:c.pdf ")).toBe("a_b_c");
    expect(sanitizeBaseName("CON")).toBe("_CON");
    expect(uniqueFileNames(["Doc", "doc", "", "?"])).toEqual([
      "Doc.pdf",
      "doc_2.pdf",
      "document-3.pdf",
      "document-4.pdf",
    ]);
  });

  it("keeps the zone inside the page", () => {
    const zone = clampZone({ x: 0.9, y: -1, width: 0.5, height: 2 });
    expect(zone.x + zone.width).toBeLessThanOrEqual(1);
    expect(zone.y).toBe(0);
    expect(zone.y + zone.height).toBeLessThanOrEqual(1);
  });
});
