import { describe, it, expect } from "vitest";
import { mergeIssuesAdditive } from "../../src/core/issues/merge";
import type { Issue } from "../../src/core/issues/types";
import type { AnnotationRange } from "../../src/core/model/types";

function mkIssue(source: string, message: string, quote?: string, startOffset?: number): Issue {
  const anchor: AnnotationRange | undefined =
    startOffset !== undefined
      ? { nodePath: [], startOffset, endOffset: startOffset + (quote?.length ?? 0), quote: quote ?? "" }
      : undefined;
  return {
    id: `${source}-${message}-${startOffset ?? ""}`,
    source: source as Issue["source"],
    severity: "info",
    message,
    ...(quote !== undefined && { quote }),
    ...(anchor !== undefined && { anchor }),
  };
}

describe("mergeIssuesAdditive (G3, ADR-0030)", () => {
  it("preserves issues from other sources", () => {
    const existing = [mkIssue("oxygen", "missing alt"), mkIssue("local", "schema error")];
    const incoming = [mkIssue("proofreader", "mixed units")];
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toHaveLength(3);
    expect(result.map((x) => x.source)).toContain("oxygen");
    expect(result.map((x) => x.source)).toContain("local");
    expect(result.map((x) => x.source)).toContain("proofreader");
  });

  it("accumulates findings from the same source on re-run (new finding is added)", () => {
    const existing = [mkIssue("proofreader", "old finding")];
    const incoming = [mkIssue("proofreader", "new finding")];
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toHaveLength(2);
    expect(result.map((x) => x.message)).toContain("old finding");
    expect(result.map((x) => x.message)).toContain("new finding");
  });

  it("deduplicates same (source, message, quote) on re-run — does not accumulate identical issues", () => {
    const existing = [mkIssue("proofreader", "mixed units", "50 Nm")];
    const incoming = [mkIssue("proofreader", "mixed units", "50 Nm")]; // exact duplicate
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toHaveLength(1);
  });

  it("deduplicates within the incoming batch by (source, message, quote)", () => {
    const incoming = [
      mkIssue("proofreader", "mixed units", "50 Nm"),
      mkIssue("proofreader", "mixed units", "50 Nm"), // duplicate
      mkIssue("proofreader", "mixed units", "80 Nm"), // different quote → keep
    ];
    const result = mergeIssuesAdditive([], incoming);
    expect(result).toHaveLength(2);
  });

  it("does NOT deduplicate issues with same message+quote but different anchor.startOffset", () => {
    const existing = [mkIssue("proofreader", "mixed units", "50 Nm", 10)];
    const incoming = [mkIssue("proofreader", "mixed units", "50 Nm", 200)]; // different offset
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toHaveLength(2);
  });

  it("keeps N existing (other source) + new proofreader findings after a run", () => {
    const existing = [mkIssue("oxygen", "a"), mkIssue("oxygen", "b")];
    const incoming = [mkIssue("proofreader", "x"), mkIssue("proofreader", "y")];
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toHaveLength(4);
  });

  it("returns existing unchanged (toBe) when incoming is empty", () => {
    const existing = [mkIssue("proofreader", "x")];
    const result = mergeIssuesAdditive(existing, []);
    expect(result).toBe(existing);
  });

  it("returns existing unchanged (toBe) when all incoming are duplicates", () => {
    const existing = [mkIssue("proofreader", "x", "quote")];
    const incoming = [mkIssue("proofreader", "x", "quote")];
    const result = mergeIssuesAdditive(existing, incoming);
    expect(result).toBe(existing);
  });
});
