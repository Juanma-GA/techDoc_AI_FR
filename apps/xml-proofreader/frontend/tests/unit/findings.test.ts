import { describe, it, expect } from "vitest";
import { parseFindings } from "../../src/core/findings/parse";
import { parseGraderResponse } from "../../src/core/grader/parser";

describe("parseFindings", () => {
  it("parses a well-formed findings array including replacement", () => {
    const json = JSON.stringify({
      findings: [
        {
          rule: "No mixed units",
          severity: "error",
          message: "Mixed units.",
          quote: "Apply 2.5 lbf pressure.",
          replacement: "Apply 11 N pressure.",
        },
      ],
    });
    const { findings, error } = parseFindings(json);
    expect(error).toBeUndefined();
    expect(findings).toHaveLength(1);
    expect(findings[0]).toEqual({
      rule: "No mixed units",
      severity: "error",
      message: "Mixed units.",
      quote: "Apply 2.5 lbf pressure.",
      replacement: "Apply 11 N pressure.",
    });
  });

  it("leaves replacement undefined when absent or non-string", () => {
    const json = JSON.stringify({
      findings: [
        { rule: "r", severity: "info", message: "m", quote: "q" },
        { rule: "r", severity: "info", message: "m", quote: "q", replacement: null },
      ],
    });
    const { findings } = parseFindings(json);
    expect(findings[0].replacement).toBeUndefined();
    expect(findings[1].replacement).toBeUndefined();
  });

  it("normalizes an unknown severity to 'warning'", () => {
    const { findings } = parseFindings(JSON.stringify({ findings: [{ severity: "critical", message: "x", quote: "" }] }));
    expect(findings[0].severity).toBe("warning");
  });

  it("reports an error (no throw) on unparseable JSON", () => {
    const { findings, error } = parseFindings("not json");
    expect(findings).toEqual([]);
    expect(error).toMatch(/unparseable/i);
  });

  it("reports an error when findings array is missing", () => {
    const { findings, error } = parseFindings(JSON.stringify({ result: [] }));
    expect(findings).toEqual([]);
    expect(error).toMatch(/findings array/i);
  });
});

describe("parseGraderResponse — suggestion comes from replacement, not rule", () => {
  const BUFFER = "<task><cmd>Apply 2.5 lbf pressure.</cmd></task>";

  it("maps replacement to Issue.suggestion and anchors by quote", () => {
    const json = JSON.stringify({
      findings: [
        {
          rule: "No mixed units",
          severity: "error",
          message: "Mixed units.",
          quote: "Apply 2.5 lbf pressure.",
          replacement: "Apply 11 N pressure.",
        },
      ],
    });
    const issues = parseGraderResponse(json, BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].suggestion).toBe("Apply 11 N pressure.");
    expect(issues[0].suggestion).not.toBe("No mixed units"); // regression: was f.rule
    expect(issues[0].anchor).toBeDefined();
    expect(issues[0].anchor!.quote).toBe("Apply 2.5 lbf pressure.");
  });

  it("leaves suggestion undefined when no replacement is given", () => {
    const json = JSON.stringify({
      findings: [{ rule: "r", severity: "info", message: "m", quote: "Apply 2.5 lbf pressure." }],
    });
    const issues = parseGraderResponse(json, BUFFER);
    expect(issues[0].suggestion).toBeUndefined();
  });

  it("emits a single info issue on malformed input", () => {
    const issues = parseGraderResponse("oops", BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("info");
    expect(issues[0].message).toMatch(/unparseable/i);
  });
});
