import { describe, it, expect } from "vitest";
import { computeMarks, type RunSpan } from "../../src/ui/viewer/IssueMarks";
import type { Issue } from "../../src/core/issues/types";

// Three rendered runs: [0,10) [10,15) [20,30) in source-offset space.
const RUNS: RunSpan[] = [
  { srcStart: 0, length: 10 },
  { srcStart: 10, length: 5 },
  { srcStart: 20, length: 10 },
];

function issue(id: string, start: number, end: number, extra: Partial<Issue> = {}): Issue {
  return {
    id,
    source: "proofreader",
    severity: "warning",
    message: "m",
    quote: "q",
    anchor: { nodePath: [], startOffset: start, endOffset: end, quote: "q" },
    ...extra,
  };
}

describe("computeMarks", () => {
  it("maps an anchor onto the run that contains it, with run-local offsets", () => {
    const specs = computeMarks(RUNS, [issue("a", 2, 6)], null);
    expect(specs).toEqual([{ issueId: "a", runIndex: 0, start: 2, end: 6, active: false }]);
  });

  it("maps anchors in later runs (offset relative to that run's srcStart)", () => {
    const specs = computeMarks(RUNS, [issue("b", 22, 28)], null);
    expect(specs).toEqual([{ issueId: "b", runIndex: 2, start: 2, end: 8, active: false }]);
  });

  it("flags the active issue", () => {
    const specs = computeMarks(RUNS, [issue("a", 0, 4), issue("b", 11, 14)], "b");
    expect(specs.find((s) => s.issueId === "a")!.active).toBe(false);
    expect(specs.find((s) => s.issueId === "b")!.active).toBe(true);
  });

  it("skips issues without an anchor", () => {
    expect(computeMarks(RUNS, [issue("a", 0, 4, { anchor: undefined })], null)).toEqual([]);
  });

  it("skips empty / inverted ranges", () => {
    expect(computeMarks(RUNS, [issue("a", 5, 5), issue("b", 6, 3)], null)).toEqual([]);
  });

  it("skips anchors that span a run boundary (not fully contained)", () => {
    // [8,12) straddles run 0 [0,10) and run 1 [10,15) → no single containing run.
    expect(computeMarks(RUNS, [issue("a", 8, 12)], null)).toEqual([]);
  });

  it("skips anchors that fall in a gap between runs", () => {
    // [16,18) is in the [15,20) gap (no run covers it).
    expect(computeMarks(RUNS, [issue("a", 16, 18)], null)).toEqual([]);
  });
});
