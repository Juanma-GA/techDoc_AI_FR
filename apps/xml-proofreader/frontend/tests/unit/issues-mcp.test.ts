import { describe, it, expect, vi } from "vitest";
import type { McpPort, McpCallResult } from "../../src/ports/McpPort";
import { OxygenIssueProvider } from "../../src/core/issues/providers/oxygen";

// ---------------------------------------------------------------------------
// Mock McpPort factory
// ---------------------------------------------------------------------------

function makeMockMcp(overrides: Partial<McpPort> = {}): McpPort {
  return {
    isAvailable: () => true,
    listTools: async () => [{ name: "validate_document", description: "Validate an XML document" }],
    callTool: async () => ({ content: [], isError: false }),
    ...overrides,
  };
}

const DITA_BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t1">
  <title>Tighten the bolt to 50 Nm.</title>
  <taskbody><steps><step><cmd>Apply torque.</cmd></step></steps></taskbody>
</task>`;

// ---------------------------------------------------------------------------
// Availability
// ---------------------------------------------------------------------------

describe("OxygenIssueProvider — isAvailable", () => {
  it("delegates to McpPort.isAvailable()", () => {
    expect(new OxygenIssueProvider(makeMockMcp({ isAvailable: () => true })).isAvailable()).toBe(true);
    expect(new OxygenIssueProvider(makeMockMcp({ isAvailable: () => false })).isAvailable()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Tool discovery
// ---------------------------------------------------------------------------

describe("OxygenIssueProvider — tool discovery", () => {
  it("returns an info issue when no validation tool is found", async () => {
    const mcp = makeMockMcp({
      listTools: async () => [{ name: "refactor_xml" }, { name: "edit_element" }],
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("info");
    expect(issues[0].message).toContain("no validation tool");
  });

  it("returns an error issue when listTools rejects", async () => {
    const mcp = makeMockMcp({
      listTools: async () => { throw new Error("connection refused"); },
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("error");
    expect(issues[0].message).toContain("cannot reach server");
  });

  it("picks the first tool whose name contains 'validat' (case-insensitive)", async () => {
    const callFn = vi.fn(async (): Promise<McpCallResult> => ({ content: [], isError: false }));
    const mcp = makeMockMcp({
      listTools: async () => [
        { name: "edit_xml" },
        { name: "Validate_Document" }, // uppercase V — must still match
        { name: "validate_schema" },
      ],
      callTool: callFn,
    });
    await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(callFn).toHaveBeenCalledWith("Validate_Document", expect.any(Object));
  });
});

// ---------------------------------------------------------------------------
// Result parsing
// ---------------------------------------------------------------------------

describe("OxygenIssueProvider — result parsing", () => {
  it("returns empty array when Oxygen reports no issues (empty content)", async () => {
    const mcp = makeMockMcp({
      callTool: async () => ({ content: [{ type: "text", text: "" }], isError: false }),
    });
    expect(await new OxygenIssueProvider(mcp).run(DITA_BUF)).toHaveLength(0);
  });

  it("parses bracketed severity lines [ERROR] and [WARNING]", async () => {
    const text = [
      "[ERROR]   file.dita:10:5: element <foo> not allowed here",
      "[WARNING] file.dita:20:1: attribute id required but missing",
    ].join("\n");
    const mcp = makeMockMcp({
      callTool: async () => ({ content: [{ type: "text", text }], isError: false }),
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(2);
    expect(issues[0].severity).toBe("error");
    expect(issues[0].source).toBe("oxygen");
    expect(issues[1].severity).toBe("warning");
  });

  it("parses structured JSON output from the tool", async () => {
    const findings = [
      { severity: "error", message: "Schema violation at line 5" },
      { severity: "warning", message: "Missing @id on <concept>", quote: "50 Nm" },
    ];
    const mcp = makeMockMcp({
      callTool: async () => ({
        content: [{ type: "text", text: JSON.stringify(findings) }],
        isError: false,
      }),
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(2);
    expect(issues[0].severity).toBe("error");
    expect(issues[1].quote).toBe("50 Nm");
    expect(issues[1].anchor).toBeDefined(); // "50 Nm" exists in DITA_BUF
  });

  it("returns an error issue when the tool reports isError", async () => {
    const mcp = makeMockMcp({
      callTool: async () => ({
        content: [{ type: "text", text: "Internal validation error" }],
        isError: true,
      }),
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("error");
    expect(issues[0].message).toContain("Internal validation error");
  });

  it("returns an error issue when callTool rejects", async () => {
    const mcp = makeMockMcp({
      callTool: async () => { throw new Error("timeout"); },
    });
    const issues = await new OxygenIssueProvider(mcp).run(DITA_BUF);
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe("error");
    expect(issues[0].message).toContain("timeout");
  });
});
