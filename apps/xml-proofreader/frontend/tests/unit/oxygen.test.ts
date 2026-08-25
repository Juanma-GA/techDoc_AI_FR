import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseXml } from "../../src/core/xml/parse";
import { serializeTree } from "../../src/core/xml/tree";
import { parseComments } from "../../src/core/oxygen/parse";
import {
  createAnnotation,
  deleteAnnotation,
  updateAnnotation,
  buildPiGroups,
} from "../../src/core/oxygen/serialize";
import { toOxygenTime, fromOxygenTime } from "../../src/core/oxygen/time";

const golden = (f: string) => readFileSync(join(__dirname, "..", "golden", f), "utf8");

describe("F4 — Oxygen timestamp round-trip", () => {
  it("formats and parses Oxygen timestamps", () => {
    const t = Date.UTC(2026, 5, 12, 10, 15, 0);
    expect(toOxygenTime(t)).toBe("20260612T101500+0000");
    expect(fromOxygenTime("20260612T101500+0000")).toBe(t);
  });
});

describe("F4 — parse oxy_* PIs into comments", () => {
  const buffer = golden("task-with-oxygen-comments.dita");
  const tree = parseXml(buffer);
  const comments = parseComments(tree, buffer);

  it("finds both annotations with author, text and colors", () => {
    expect(comments.length).toBe(2);
    const [c1, c2] = comments;
    expect(c1.author).toBe("Maria Ruiz");
    expect(c1.color).toBe("yellow");
    expect(c1.text).toContain("secondary suspension");
    expect(c1.resolved).toBe(false);
    expect(c1.anchor.quote).toContain("the primary suspension");

    expect(c2.color).toBe("pink");
    expect(c2.resolved).toBe(true); // flag="done"
    expect(c2.text).toContain("130 Nm");
    expect(c2.anchor.quote).toBe("set to 120 Nm");
  });

  it("unescapes attribute entities in comment text", () => {
    const buf = `<p>x<?oxy_comment_start author="A" timestamp="20260101T000000+0000" comment="a &amp; b &lt; c"?>` +
      `<?oxy_custom_start type="oxy_content_highlight" color="255,243,163"?>y<?oxy_custom_end?><?oxy_comment_end?>z</p>`;
    const cs = parseComments(parseXml(buf), buf);
    expect(cs[0].text).toBe("a & b < c");
  });
});

describe("F4 — serialize round-trips byte-for-byte", () => {
  it("create then delete returns the original buffer exactly", () => {
    const buffer = "<p>Tighten to 120 Nm now.</p>";
    const start = buffer.indexOf("120 Nm");
    const end = start + "120 Nm".length;
    const annotated = createAnnotation(buffer, start, end, {
      author: "Maria Ruiz",
      timestamp: Date.UTC(2026, 0, 1, 9, 0, 0),
      text: "Should be 130 Nm",
      color: "pink",
      resolved: false,
    });
    expect(annotated).toContain("oxy_comment_start");
    expect(annotated).toContain('color="255,201,222"');

    // Re-parse to recover the annotation's spans, then delete it.
    const c = parseComments(parseXml(annotated), annotated)[0];
    const restored = deleteAnnotation(annotated, c.spans);
    expect(restored).toBe(buffer);
  });

  it("preserves the whole document when annotating inside it", () => {
    const buffer = golden("concept-namespaced.dita");
    const text = "blended braking system";
    const start = buffer.indexOf(text);
    const annotated = createAnnotation(buffer, start, start + text.length, {
      author: "SME",
      timestamp: Date.UTC(2026, 0, 1, 12, 0, 0),
      text: "Confirm wording",
      color: "green",
      resolved: false,
    });
    // The positional tree of the annotated doc still round-trips (well-formed).
    expect(serializeTree(parseXml(annotated), annotated)).toBe(annotated);
    // And removing the annotation restores the original byte for byte.
    const c = parseComments(parseXml(annotated), annotated).find((x) => x.text === "Confirm wording")!;
    expect(deleteAnnotation(annotated, c.spans)).toBe(buffer);
  });

  it("updates text/color/resolved in place", () => {
    const buffer = "<p>value is 120 Nm.</p>";
    const start = buffer.indexOf("120 Nm");
    let buf = createAnnotation(buffer, start, start + 6, {
      author: "A", timestamp: Date.UTC(2026, 0, 1), text: "old", color: "yellow", resolved: false,
    });
    let c = parseComments(parseXml(buf), buf)[0];
    buf = updateAnnotation(buf, c.spans, {
      author: "A", timestamp: c.timestamp, text: "new note", color: "blue", resolved: true,
    });
    c = parseComments(parseXml(buf), buf)[0];
    expect(c.text).toBe("new note");
    expect(c.color).toBe("blue");
    expect(c.resolved).toBe(true);
    // inner text untouched
    expect(buf).toContain(">120 Nm<");
  });

  it("emits a comment-less highlight as an oxy_custom pair only", () => {
    const { open, close } = buildPiGroups({
      author: "", timestamp: Date.now(), text: "", color: "yellow", resolved: false,
    });
    expect(open).toBe('<?oxy_custom_start type="oxy_content_highlight" color="255,243,163"?>');
    expect(close).toBe("<?oxy_custom_end?>");
    expect(open).not.toContain("oxy_comment_start");
  });
});
