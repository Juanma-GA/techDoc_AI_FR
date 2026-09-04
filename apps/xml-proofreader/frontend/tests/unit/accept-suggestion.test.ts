import { describe, it, expect, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";
import type { Issue } from "../../src/core/issues/types";

const BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><taskbody><context><p>Apply 2.5 lbf pressure before service.</p></context></taskbody></task>
`;

function issue(over: Partial<Issue> = {}): Issue {
  return {
    id: "i1",
    source: "proofreader",
    severity: "warning",
    message: "Mixed units.",
    quote: "Apply 2.5 lbf pressure",
    suggestion: "Apply 11 N pressure",
    ...over,
  };
}

// E3 (ADR-0020, supersedes ADR-0015; restores ADR-0003): accepting a suggestion
// must NOT edit the document text. It anchors a standard comment over the quoted
// range whose body carries the suggestion. The original content is never
// rewritten (CLAUDE.md §7).
describe("acceptSuggestion (E3) — creates a comment, never edits the XML text", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "t.dita", BUF);
  });

  it("keeps the document text intact and anchors a comment carrying the suggestion", () => {
    const s = useStore.getState();
    s.setIssues([issue()]);
    s.acceptSuggestion("i1");
    const buf = useStore.getState().buffer;
    // The original prose is untouched (still contiguous, just wrapped in PIs).
    expect(buf).toContain("Apply 2.5 lbf pressure");
    // A comment PI was spliced in, and its body carries message + suggestion.
    expect(buf).toContain("oxy_comment_start");
    expect(buf).toContain("Mixed units. — Sugerencia: Apply 11 N pressure");
    // Exactly one comment now exists and the issue is gone; buffer is dirty.
    expect(useStore.getState().comments).toHaveLength(1);
    expect(useStore.getState().issues).toHaveLength(0);
    expect(useStore.getState().dirty).toBe(true);
    // The created comment becomes active (mirrors addAnnotation).
    expect(useStore.getState().activeId).toBe(useStore.getState().comments[0].id);
  });

  it("matches a quote with normalized whitespace and anchors over the source span", () => {
    const s = useStore.getState();
    s.setIssues([issue({ quote: "Apply   2.5\nlbf pressure" })]);
    s.acceptSuggestion("i1");
    const buf = useStore.getState().buffer;
    expect(buf).toContain("Apply 2.5 lbf pressure"); // text unchanged
    expect(buf).toContain("oxy_comment_start");
    expect(useStore.getState().comments).toHaveLength(1);
  });

  it("matches a quote that differs only in capitalization (E2 case-insensitive)", () => {
    const s = useStore.getState();
    s.setIssues([issue({ quote: "APPLY 2.5 LBF PRESSURE" })]);
    s.acceptSuggestion("i1");
    const buf = useStore.getState().buffer;
    expect(buf).toContain("Apply 2.5 lbf pressure"); // original casing preserved
    expect(buf).toContain("oxy_comment_start");
    expect(useStore.getState().comments).toHaveLength(1);
    expect(useStore.getState().issues).toHaveLength(0);
  });

  it("does nothing when the quote cannot be located (no mutation, issue stays)", () => {
    const s = useStore.getState();
    s.setIssues([issue({ id: "i2", quote: "text that is absent" })]);
    const before = useStore.getState().buffer;
    s.acceptSuggestion("i2");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().comments).toHaveLength(0);
    expect(useStore.getState().issues.find((x) => x.id === "i2")).toBeDefined();
  });

  it("does not anchor a quote that crosses element boundaries", () => {
    const s = useStore.getState();
    s.setIssues([issue({ id: "i3", quote: "context Apply" })]); // crosses <context><p>
    const before = useStore.getState().buffer;
    s.acceptSuggestion("i3");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().comments).toHaveLength(0);
    expect(useStore.getState().issues.find((x) => x.id === "i3")).toBeDefined();
  });

  // G2 fix (review): stored anchor whose startOffset falls inside a tag must be rejected (no mutation).
  it("does not use a stored anchor whose offset lands inside a tag (stale anchor guard)", () => {
    const s = useStore.getState();
    // In BUF, the opening <task id="t"> tag starts at position 39 (after the XML decl+newline).
    // We pick an offset inside the attribute text "t" of id="t" — clearly inside a tag.
    const insideTagOffset = BUF.indexOf('id="t"') + 4; // points at '"t"', inside the tag
    s.setIssues([issue({
      id: "stale",
      quote: "text that is absent", // locateQuote and locateQuotePartial both fail
      anchor: { nodePath: [], startOffset: insideTagOffset, endOffset: insideTagOffset + 1, quote: "t" },
    })]);
    const before = useStore.getState().buffer;
    s.acceptSuggestion("stale");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().comments).toHaveLength(0);
    expect(useStore.getState().issues.find((x) => x.id === "stale")).toBeDefined();
  });

  it("ignores issues without a suggestion", () => {
    const s = useStore.getState();
    s.setIssues([issue({ id: "i4", suggestion: undefined })]);
    const before = useStore.getState().buffer;
    s.acceptSuggestion("i4");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().comments).toHaveLength(0);
  });

  // G2 (ADR-0032): entity-normalized quote finds buffer's &amp; entity.
  it("anchors a quote with & where the buffer has &amp; (entity normalization tier)", () => {
    const bufWithAmp = `<?xml version="1.0"?>\n<task id="t"><taskbody><context><p>Q&amp;A apply.</p></context></taskbody></task>\n`;
    useStore.getState().loadBuffer(null, "t.dita", bufWithAmp);
    const s = useStore.getState();
    s.setIssues([issue({ quote: "Q&A apply." })]);
    s.acceptSuggestion("i1");
    expect(useStore.getState().buffer).toContain("oxy_comment_start");
    expect(useStore.getState().comments).toHaveLength(1);
  });

  // G2 (ADR-0032): partial locate — quote spans inline element, partial anchor created.
  it("creates a comment on the longest safe prefix when quote crosses an inline tag", () => {
    // "Apply 2.5 lbf" is safe text; " pressure" is in the same run so let's cross a tag.
    const crossBuf = `<?xml version="1.0"?>\n<task id="t"><taskbody><context><p>Apply 2.5 <b>lbf</b> pressure.</p></context></taskbody></task>\n`;
    useStore.getState().loadBuffer(null, "t.dita", crossBuf);
    const s = useStore.getState();
    s.setIssues([issue({ quote: "Apply 2.5 lbf pressure" })]);
    s.acceptSuggestion("i1");
    // Full quote crosses tags; partial locate should find "Apply 2.5" or similar prefix.
    expect(useStore.getState().buffer).toContain("oxy_comment_start");
    expect(useStore.getState().comments).toHaveLength(1);
    // The issue should be consumed.
    expect(useStore.getState().issues).toHaveLength(0);
  });

  // G2 (ADR-0032): stored anchor fallback when quote is absent but anchor exists.
  it("uses the stored issue anchor when quote is absent but anchor exists", () => {
    const s = useStore.getState();
    const pStart = BUF.indexOf("Apply");
    const pEnd = pStart + "Apply 2.5 lbf pressure".length;
    s.setIssues([issue({
      id: "anch1",
      quote: undefined,
      anchor: { nodePath: [], startOffset: pStart, endOffset: pEnd, quote: "Apply 2.5 lbf pressure" },
    })]);
    s.acceptSuggestion("anch1");
    expect(useStore.getState().buffer).toContain("oxy_comment_start");
    expect(useStore.getState().comments).toHaveLength(1);
    expect(useStore.getState().issues).toHaveLength(0);
  });

  // F2 (ADR-0025): caller passes the color; the store must use it, not hardcode "yellow".
  it("uses the color argument passed by the caller (F2)", () => {
    const s = useStore.getState();
    s.setIssues([issue()]);
    s.acceptSuggestion("i1", "green");
    const buf = useStore.getState().buffer;
    // "green" serializes as RGB 189,245,200 in the Oxygen PI.
    expect(buf).toContain('color="189,245,200"');
    // "yellow" must NOT appear as the color (it is the default when no arg is passed).
    expect(buf).not.toContain('color="255,243,163"');
    // The comment itself is anchored and carries the suggestion text.
    expect(useStore.getState().comments[0].color).toBe("green");
  });
});
