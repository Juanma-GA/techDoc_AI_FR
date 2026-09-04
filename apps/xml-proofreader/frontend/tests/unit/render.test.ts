import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseXml } from "../../src/core/xml/parse";
import { buildRenderedDoc } from "../../src/core/render/ditaModel";
import { buildInlines } from "../../src/core/render/inlines";
import { resolveBaseType } from "../../src/core/render/fallback";
import type { PosNode } from "../../src/core/model/types";

function load(file: string) {
  const buffer = readFileSync(join(__dirname, "..", "golden", file), "utf8");
  return { buffer, tree: parseXml(buffer) };
}

describe("F2 — base type resolution", () => {
  it("resolves from @class (specialization ancestry → base)", () => {
    const { tree } = load("reference-with-trackchanges.dita");
    const root = (tree.children ?? []).find((c) => c.kind === "element") as PosNode;
    expect(resolveBaseType(root)).toBe("topic/topic");
    const p = findName(tree, "p");
    expect(resolveBaseType(p!)).toBe("topic/p");
  });

  it("falls back to GI when @class is absent", () => {
    const { tree } = load("task-with-oxygen-comments.dita");
    const cmd = findName(tree, "cmd");
    expect(resolveBaseType(cmd!)).toBe("task/cmd");
    const step = findName(tree, "step");
    expect(resolveBaseType(step!)).toBe("task/step");
  });
});

describe("F2 — rendered document model", () => {
  it("extracts title and subtitle", () => {
    const { tree, buffer } = load("task-with-oxygen-comments.dita");
    const doc = buildRenderedDoc(tree, buffer);
    expect(doc.title?.map((i) => i.text).join("")).toContain("Motor Bogie Maintenance");
    expect(doc.subtitle?.map((i) => i.text).join("")).toContain("inspection procedure");
  });

  it("renders steps as step blocks", () => {
    const { tree, buffer } = load("task-with-oxygen-comments.dita");
    const doc = buildRenderedDoc(tree, buffer);
    const steps = doc.blocks.find((b) => b.kind === "steps");
    expect(steps && steps.kind === "steps" && steps.steps.length).toBe(3);
  });

  it("carries highlight decoration with color and comment key on runs", () => {
    const { tree, buffer } = load("task-with-oxygen-comments.dita");
    const doc = buildRenderedDoc(tree, buffer);
    const allRuns = collectRuns(doc);
    const highlighted = allRuns.filter((r) => r.color);
    expect(highlighted.length).toBeGreaterThanOrEqual(2);
    const withComment = allRuns.filter((r) => r.commentKey !== undefined);
    expect(withComment.length).toBeGreaterThanOrEqual(2);
    // The run carries the exact source offset of its first character.
    const target = allRuns.find((r) => r.text.startsWith("the primary suspension"));
    expect(target).toBeDefined();
    expect(buffer.slice(target!.srcStart, target!.srcStart + 20)).toBe(target!.text.slice(0, 20));
  });

  it("renders a CALS table with header and rows", () => {
    const { tree, buffer } = load("concept-namespaced.dita");
    const doc = buildRenderedDoc(tree, buffer);
    const table = doc.blocks.find((b) => b.kind === "table");
    expect(table && table.kind === "table").toBe(true);
    if (table && table.kind === "table") {
      expect(table.headRows[0].cells.length).toBe(2);
      expect(table.bodyRows.length).toBe(2);
    }
  });

  it("builds an outline from section headings", () => {
    const { tree, buffer } = load("reference-with-trackchanges.dita");
    const doc = buildRenderedDoc(tree, buffer);
    expect(doc.outline.map((o) => o.text)).toContain("Bogie fasteners");
  });
});

describe("B6c — xref renders as a LinkRun", () => {
  const xml =
    `<?xml version="1.0"?>\n` +
    `<topic id="t"><title>T</title><body>` +
    `<p>Intro <xref href="#sec1">see section</xref> end.</p>` +
    `<p>Empty <xref href="other.dita#x"/> ref.</p>` +
    `</body></topic>`;

  function links(doc: ReturnType<typeof buildRenderedDoc>) {
    const out: import("../../src/core/render/model").LinkRun[] = [];
    for (const b of doc.blocks) {
      if (b.kind === "para") {
        for (const inl of b.inlines) if (inl.kind === "link") out.push(inl);
      }
    }
    return out;
  }

  it("emits a link run with the href and the visible label", () => {
    const tree = parseXml(xml);
    const doc = buildRenderedDoc(tree, xml);
    const ls = links(doc);
    const sec = ls.find((l) => l.href === "#sec1");
    expect(sec).toBeDefined();
    expect(sec!.text).toBe("see section");
  });

  it("srcStart points at the link's text, not the '<xref' tag (R2)", () => {
    const tree = parseXml(xml);
    const doc = buildRenderedDoc(tree, xml);
    const sec = links(doc).find((l) => l.href === "#sec1")!;
    // The offset must land on the visible text so selection→buffer mapping holds.
    expect(xml.slice(sec.srcStart, sec.srcStart + 3)).toBe("see");
  });

  it("gives an empty/self-closing xref a neutral label, not the raw href", () => {
    const tree = parseXml(xml);
    const doc = buildRenderedDoc(tree, xml);
    const empty = links(doc).find((l) => l.href === "other.dita#x")!;
    expect(empty).toBeDefined();
    expect(empty.text).not.toContain("other.dita");
  });
});

describe("F1 — commentKey keys to thread root, not innermost reply", () => {
  // XML with a thread: root comment wraps a reply PI inside the same text span.
  // oxy_comment_start id=1 (root), then oxy_comment_start id=2 (reply), then text, then both ends.
  const xml =
    `<?xml version="1.0"?><topic id="t"><title>T</title><body><p>` +
    `<?oxy_comment_start author="a" timestamp="20240101T000000" comment="root" id="1"?>` +
    `<?oxy_comment_start author="b" timestamp="20240102T000000" comment="reply" mid="1"?>` +
    `annotated text` +
    `<?oxy_comment_end mid="1"?><?oxy_comment_end?>` +
    `</p></body></topic>`;

  it("run inside a thread carries the ROOT comment key, not the innermost", () => {
    const tree = parseXml(xml);
    const body = findName(tree, "p")!;
    const runs = buildInlines(body.children ?? [], xml);
    const annotated = runs.find((r) => r.text === "annotated text");
    expect(annotated).toBeDefined();
    // The commentKey must be the offset of the FIRST (root) oxy_comment_start PI.
    const rootPiOffset = xml.indexOf("<?oxy_comment_start author=\"a\"");
    const replyPiOffset = xml.indexOf("<?oxy_comment_start author=\"b\"");
    expect(annotated!.commentKey).toBe(rootPiOffset);
    expect(annotated!.commentKey).not.toBe(replyPiOffset);
  });

  it("run without replies still carries the single comment key (regression)", () => {
    const singleXml =
      `<?xml version="1.0"?><topic id="t"><title>T</title><body><p>` +
      `<?oxy_comment_start author="a" timestamp="20240101T000000" comment="only"?>` +
      `solo text` +
      `<?oxy_comment_end?>` +
      `</p></body></topic>`;
    const tree = parseXml(singleXml);
    const body = findName(tree, "p")!;
    const runs = buildInlines(body.children ?? [], singleXml);
    const solo = runs.find((r) => r.text === "solo text");
    expect(solo).toBeDefined();
    const piOffset = singleXml.indexOf("<?oxy_comment_start");
    expect(solo!.commentKey).toBe(piOffset);
  });
});

// helpers
function findName(node: PosNode, name: string): PosNode | null {
  if (node.kind === "element" && node.name === name) return node;
  for (const c of node.children ?? []) {
    const r = findName(c, name);
    if (r) return r;
  }
  return null;
}
function collectRuns(doc: ReturnType<typeof buildRenderedDoc>) {
  const runs: { text: string; color?: string; commentKey?: number; srcStart: number }[] = [];
  const visitInlines = (inls: { text: string; color?: string; commentKey?: number; srcStart: number }[]) =>
    inls.forEach((i) => runs.push(i));
  const visitBlock = (b: import("../../src/core/render/model").Block) => {
    switch (b.kind) {
      case "para": case "heading": case "note": case "doc-title": case "subtitle":
        visitInlines(b.inlines); break;
      case "list": b.items.forEach((it) => it.forEach(visitBlock)); break;
      case "steps": b.steps.forEach((st) => st.forEach(visitBlock)); break;
      case "table":
        [...b.headRows, ...b.bodyRows].forEach((row) => row.cells.forEach((c) => visitInlines(c.inlines)));
        if (b.caption) visitInlines(b.caption); break;
      case "figure": if (b.caption) visitInlines(b.caption); break;
      case "generic": visitInlines(b.inlines); b.blocks.forEach(visitBlock); break;
    }
  };
  doc.blocks.forEach(visitBlock);
  return runs;
}
