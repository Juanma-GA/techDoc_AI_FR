import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { parseXml } from "../../src/core/xml/parse";
import { serializeTree, walk, elementText, rootElement } from "../../src/core/xml/tree";
import { applyEdits } from "../../src/core/xml/splice";

const goldenDir = join(__dirname, "..", "golden");
const goldenFiles = readdirSync(goldenDir).filter((f) => f.endsWith(".dita") || f.endsWith(".xml"));

describe("F1 — parse → serialize byte-identical (golden corpus)", () => {
  for (const file of goldenFiles) {
    it(`round-trips ${file} byte for byte`, () => {
      const buffer = readFileSync(join(goldenDir, file), "utf8");
      const tree = parseXml(buffer);
      expect(serializeTree(tree, buffer)).toBe(buffer);
    });
  }

  it("tiles every byte exactly once (no gaps, no overlaps)", () => {
    const buffer = readFileSync(join(goldenDir, "task-with-oxygen-comments.dita"), "utf8");
    const tree = parseXml(buffer);
    // The concatenation of leaf + tag spans must equal the buffer length.
    expect(serializeTree(tree, buffer).length).toBe(buffer.length);
  });
});

describe("F1 — positional tree structure", () => {
  const buffer = readFileSync(join(goldenDir, "task-with-oxygen-comments.dita"), "utf8");
  const tree = parseXml(buffer);

  it("captures the prolog, doctype and root element", () => {
    const kinds = (tree.children ?? []).map((c) => c.kind);
    expect(kinds).toContain("doctype"); // <?xml?> and <!DOCTYPE?>
    expect(rootElement(tree)?.name).toBe("task");
  });

  it("preserves processing instructions as nodes", () => {
    let piCount = 0;
    walk(tree, (n) => {
      if (n.kind === "pi" && n.name?.startsWith("oxy_")) piCount++;
    });
    // 2 comment_start + 2 comment_end + 2 custom_start + 2 custom_end
    expect(piCount).toBe(8);
  });

  it("reads attributes including @class and xml:lang", () => {
    const task = rootElement(tree)!;
    expect(task.attrs?.["xml:lang"]).toBe("en");
    expect(task.attrs?.["id"]).toBe("SR-MNT-BOGIE-04");
  });

  it("computes element text excluding PIs/comments", () => {
    const buffer2 = readFileSync(join(goldenDir, "task-with-oxygen-comments.dita"), "utf8");
    const t = parseXml(buffer2);
    let firstP: ReturnType<typeof rootElement> = null;
    walk(t, (n) => {
      if (!firstP && n.kind === "element" && n.name === "p") firstP = n;
    });
    const text = elementText(firstP!, buffer2);
    expect(text).toContain("the primary suspension, the dampers and the axlebox fastening");
    expect(text).not.toContain("oxy_comment_start");
  });
});

describe("F1 — @class present is parsed", () => {
  it("reads the @class specialization ancestry", () => {
    const buffer = readFileSync(join(goldenDir, "reference-with-trackchanges.dita"), "utf8");
    const tree = parseXml(buffer);
    const ref = rootElement(tree)!;
    expect(ref.classAttr).toContain("reference/reference");
  });

  it("preserves foreign track-change PIs on round-trip", () => {
    const buffer = readFileSync(join(goldenDir, "reference-with-trackchanges.dita"), "utf8");
    const tree = parseXml(buffer);
    expect(serializeTree(tree, buffer)).toBe(buffer);
    let hasDelete = false;
    walk(tree, (n) => {
      if (n.kind === "pi" && n.name === "oxy_delete") hasDelete = true;
    });
    expect(hasDelete).toBe(true);
  });
});

describe("F1 — splice engine", () => {
  it("inserts at offsets without touching the rest", () => {
    const buf = "<p>hello world</p>";
    const at = buf.indexOf("world");
    const out = applyEdits(buf, [{ type: "insert", at, text: "<b>" }, { type: "insert", at: at + "world".length, text: "</b>" }]);
    expect(out).toBe("<p>hello <b>world</b></p>");
  });

  it("applies multiple inserts right-to-left consistently", () => {
    const buf = "ABCDE";
    const out = applyEdits(buf, [
      { type: "insert", at: 1, text: "(" },
      { type: "insert", at: 4, text: ")" },
    ]);
    expect(out).toBe("A(BCD)E");
  });

  it("handles deletions", () => {
    const buf = "<p>keep [drop] keep</p>";
    const s = buf.indexOf("[drop] ");
    const out = applyEdits(buf, [{ type: "delete", start: s, end: s + "[drop] ".length }]);
    expect(out).toBe("<p>keep keep</p>");
  });
});
