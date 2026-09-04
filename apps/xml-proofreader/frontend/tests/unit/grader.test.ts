import { describe, it, expect, vi } from "vitest";
import type { LlmPort } from "../../src/ports/LlmPort";
import { AIGrader } from "../../src/core/grader/AIGrader";
import { parseGraderResponse } from "../../src/core/grader/parser";
import { buildGraderRequest, CONTEXT_LIMIT_THRESHOLD } from "../../src/core/grader/prompt";

// ---------------------------------------------------------------------------
// Mock LlmPort factory
// ---------------------------------------------------------------------------
function mockLlm(responseText: string, available = true): LlmPort {
  return {
    isAvailable: () => available,
    complete: vi.fn().mockResolvedValue(responseText),
  };
}

const SAMPLE_BUFFER = `<task id="t1">
  <title>Brake adjustment</title>
  <steps>
    <step><cmd>Torque the bolt to 50 Nm.</cmd></step>
    <step><cmd>Apply 2.5 lbf pressure.</cmd></step>
  </steps>
</task>`;

const RULES = [
  "Every torque value must cite the applicable technical note or standard.",
  "Do not mix measurement unit systems within a procedure (SI only).",
];

// ---------------------------------------------------------------------------
// parseGraderResponse
// ---------------------------------------------------------------------------
describe("parseGraderResponse — valid JSON", () => {
  it("parses a well-formed findings array into Issue[]", () => {
    const json = JSON.stringify({
      findings: [
        {
          rule: RULES[0],
          severity: "warning",
          message: "Torque value '50 Nm' does not cite a standard.",
          quote: "Torque the bolt to 50 Nm.",
        },
        {
          rule: RULES[1],
          severity: "error",
          message: "Mixed units: Nm (SI) and lbf (imperial).",
          quote: "Apply 2.5 lbf pressure.",
        },
      ],
    });

    const issues = parseGraderResponse(json, SAMPLE_BUFFER);
    expect(issues).toHaveLength(2);
    expect(issues[0].source).toBe("proofreader");
    expect(issues[0].severity).toBe("warning");
    expect(issues[0].quote).toBe("Torque the bolt to 50 Nm.");
    expect(issues[1].severity).toBe("error");
    expect(issues[1].quote).toBe("Apply 2.5 lbf pressure.");
  });

  it("anchors findings by quote when the quote is present in the buffer", () => {
    const json = JSON.stringify({
      findings: [
        { severity: "info", message: "ok", quote: "Torque the bolt to 50 Nm." },
      ],
    });
    const issues = parseGraderResponse(json, SAMPLE_BUFFER);
    expect(issues[0].anchor).toBeDefined();
    const anchor = issues[0].anchor!;
    expect(anchor.quote).toBe("Torque the bolt to 50 Nm.");
    expect(anchor.startOffset).toBeGreaterThanOrEqual(0);
    expect(anchor.endOffset).toBe(anchor.startOffset + "Torque the bolt to 50 Nm.".length);
  });

  it("leaves anchor undefined when the quote is not in the buffer", () => {
    const json = JSON.stringify({
      findings: [{ severity: "info", message: "ghost", quote: "this text is not in the buffer" }],
    });
    const issues = parseGraderResponse(json, SAMPLE_BUFFER);
    expect(issues[0].anchor).toBeUndefined();
  });

  it("returns an info issue when findings array is empty", () => {
    // Empty array is valid — just no issues
    const json = JSON.stringify({ findings: [] });
    const issues = parseGraderResponse(json, SAMPLE_BUFFER);
    expect(issues).toHaveLength(0);
  });

  it("normalises an unknown severity to 'warning'", () => {
    const json = JSON.stringify({
      findings: [{ severity: "critical", message: "bad", quote: "" }],
    });
    const issues = parseGraderResponse(json, SAMPLE_BUFFER);
    expect(issues[0].severity).toBe("warning");
  });
});

describe("parseGraderResponse — malformed input", () => {
  it("returns an info issue when the response is not JSON", () => {
    const issues = parseGraderResponse("not json at all", SAMPLE_BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("info");
    expect(issues[0].message).toMatch(/unparseable/i);
  });

  it("returns an info issue when findings is missing", () => {
    const issues = parseGraderResponse(JSON.stringify({ result: [] }), SAMPLE_BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].message).toMatch(/findings array/i);
  });
});

// ---------------------------------------------------------------------------
// buildGraderRequest
// ---------------------------------------------------------------------------
describe("buildGraderRequest", () => {
  it("embeds the rules and buffer in the request", () => {
    const req = buildGraderRequest(RULES, SAMPLE_BUFFER, "claude-sonnet-4-6");
    expect(req.model).toBe("claude-sonnet-4-6");
    expect(req.jsonMode).toBe(true);
    expect(req.content).toContain(RULES[0]);
    expect(req.content).toContain(SAMPLE_BUFFER);
  });

  it("sets a default maxTokens when not supplied", () => {
    const req = buildGraderRequest(RULES, SAMPLE_BUFFER, "model");
    expect(req.maxTokens).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// AIGrader — IssueProvider integration (with mocked LlmPort)
// ---------------------------------------------------------------------------
describe("AIGrader", () => {
  it("returns an info issue when no rules are configured", async () => {
    const grader = new AIGrader(mockLlm("{}"), () => [], () => "model");
    const issues = await grader.run(SAMPLE_BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("info");
    expect(issues[0].message).toMatch(/no proofreading rules/i);
  });

  it("returns an info issue when the document exceeds the context threshold", async () => {
    const huge = "x".repeat(CONTEXT_LIMIT_THRESHOLD + 1);
    const grader = new AIGrader(mockLlm("{}"), () => RULES, () => "model");
    const issues = await grader.run(huge);
    expect(issues).toHaveLength(1);
    expect(issues[0].message).toMatch(/context limit/i);
  });

  it("calls LlmPort.complete and returns parsed issues", async () => {
    const llmResponse = JSON.stringify({
      findings: [
        { rule: RULES[1], severity: "error", message: "Mixed units.", quote: "Apply 2.5 lbf pressure." },
      ],
    });
    const llm = mockLlm(llmResponse);
    const grader = new AIGrader(llm, () => RULES, () => "claude-sonnet-4-6");

    const issues = await grader.run(SAMPLE_BUFFER);

    expect(llm.complete).toHaveBeenCalledOnce();
    expect(issues).toHaveLength(1);
    expect(issues[0].source).toBe("proofreader");
    expect(issues[0].severity).toBe("error");
    expect(issues[0].anchor).toBeDefined();
  });

  it("isAvailable delegates to the LlmPort", () => {
    const graderOn = new AIGrader(mockLlm("{}", true), () => RULES, () => "m");
    const graderOff = new AIGrader(mockLlm("{}", false), () => RULES, () => "m");
    expect(graderOn.isAvailable()).toBe(true);
    expect(graderOff.isAvailable()).toBe(false);
  });

  it("id and label are correct", () => {
    const grader = new AIGrader(mockLlm("{}"), () => [], () => "m");
    expect(grader.id).toBe("proofreader");
    expect(grader.label).toBe("AI Proofreader");
  });

  it("returns an info issue when the LLM returns malformed JSON", async () => {
    const grader = new AIGrader(mockLlm("oops"), () => RULES, () => "model");
    const issues = await grader.run(SAMPLE_BUFFER);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("info");
    expect(issues[0].message).toMatch(/unparseable/i);
  });
});
