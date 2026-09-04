// Tests for Chunk 25 (D7): the Oxygen MCP is invoked ONLY on demand.
//
// Invariants (architecture-plan §15.10, ADR-0018):
//   • Opening a document (runProviders) must NOT spawn Oxygen.
//   • A normal chat message must NOT call listTools() (no implicit spawn).
//   • runOxygenCheck() IS the explicit trigger for the Oxygen provider.
//   • Once the tools cache is primed (listMcpTools), sendChat advertises tools
//     from the cache without re-spawning.
//
// store.ts loads these adapters via dynamic import(), so the mock factories run
// lazily at call time (same pattern as chat-mcp-actions.test.ts).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { McpPort, McpTool } from "../../src/ports/McpPort";
import type { Issue } from "../../src/core/issues/types";

// ── TauriMcp mock (spied so we can assert it is NOT constructed on load) ──────
const mockMcpIsAvailable = vi.fn<() => boolean>();
const mockListTools = vi.fn<() => Promise<McpTool[]>>();
const makeTauriMcpSpy = vi.fn((): McpPort => ({
  isAvailable: mockMcpIsAvailable,
  listTools: mockListTools,
  callTool: vi.fn(),
}));
vi.mock("../../src/adapters/tauri/TauriMcp", () => ({ makeTauriMcp: makeTauriMcpSpy }));

// ── OxygenIssueProvider mock ─────────────────────────────────────────────────
const mockOxyAvailable = vi.fn<() => boolean>();
const mockOxyRun = vi.fn<() => Promise<Issue[]>>();
vi.mock("../../src/core/issues/providers/oxygen", () => ({
  OxygenIssueProvider: class {
    constructor(_mcp: unknown) {}
    isAvailable() { return mockOxyAvailable(); }
    run() { return mockOxyRun(); }
  },
}));

// ── LLM mock (capture the system prompt sent by sendChat) ─────────────────────
const completeSpy = vi.fn<(req: { system: string }) => Promise<string>>();
vi.mock("../../src/adapters/tauri/TauriLlm", () => ({
  makeLlmPortFromSettings: () => ({ isAvailable: () => true, complete: completeSpy }),
}));

import { useStore } from "../../src/ui/store";

const DOC = "<concept id=\"c1\"><title>T</title><conbody><p>Hello world.</p></conbody></concept>";

function chatHook() {
  return (window as unknown as { __docreview: { __chat: { reset: () => void } } }).__docreview.__chat;
}

beforeEach(() => {
  makeTauriMcpSpy.mockClear();
  mockMcpIsAvailable.mockReset();
  mockListTools.mockReset().mockResolvedValue([]);
  mockOxyAvailable.mockReset();
  mockOxyRun.mockReset().mockResolvedValue([]);
  completeSpy.mockReset().mockResolvedValue("ok");
  chatHook().reset(); // clears chatLlmOverride + mcpToolsCache
  (window as unknown as { __TAURI__?: unknown }).__TAURI__ = {}; // make isTauri() true
});

afterEach(() => {
  delete (window as unknown as { __TAURI__?: unknown }).__TAURI__;
});

describe("runProviders (document load) — no Oxygen spawn", () => {
  it("does not construct the Oxygen MCP nor run the Oxygen provider", async () => {
    useStore.getState().loadBuffer(null, "doc.dita", DOC);
    await useStore.getState().runProviders();
    expect(makeTauriMcpSpy).not.toHaveBeenCalled();
    expect(mockOxyRun).not.toHaveBeenCalled();
  });
});

describe("runOxygenCheck (explicit on-demand trigger)", () => {
  it("runs the Oxygen provider and merges its issues when available", async () => {
    useStore.getState().loadBuffer(null, "doc.dita", DOC);
    await useStore.getState().runProviders();
    // Pre-seed: one stale Oxygen issue + one local issue.
    useStore.getState().setIssues([
      { id: "old-oxy", source: "oxygen", severity: "warning", message: "stale" },
      { id: "local-1", source: "schema", severity: "info", message: "keep me" },
    ]);
    mockOxyAvailable.mockReturnValue(true);
    mockOxyRun.mockResolvedValue([
      { id: "oxy-new", source: "oxygen", severity: "error", message: "fresh oxygen finding" },
    ]);

    await useStore.getState().runOxygenCheck();

    expect(makeTauriMcpSpy).toHaveBeenCalled();
    expect(mockOxyRun).toHaveBeenCalledOnce();
    const issues = useStore.getState().issues;
    // Stale oxygen issue dropped, local kept, fresh oxygen added.
    expect(issues.find((i) => i.id === "old-oxy")).toBeUndefined();
    expect(issues.find((i) => i.id === "local-1")).toBeDefined();
    expect(issues.find((i) => i.id === "oxy-new")).toBeDefined();
  });

  it("toasts and does not run the provider when MCP is not configured", async () => {
    useStore.getState().loadBuffer(null, "doc.dita", DOC);
    mockOxyAvailable.mockReturnValue(false);

    await useStore.getState().runOxygenCheck();

    expect(mockOxyRun).not.toHaveBeenCalled();
  });
});

describe("sendChat — never spawns the MCP implicitly", () => {
  it("does not call listTools(); omits the tools section when cache is empty", async () => {
    useStore.getState().loadBuffer(null, "doc.dita", DOC);
    await useStore.getState().sendChat("hi there");

    expect(mockListTools).not.toHaveBeenCalled();
    const sentSystem = completeSpy.mock.calls[0][0].system;
    expect(sentSystem).not.toContain("Available MCP tools");
  });

  it("advertises tools from the cache (primed by listMcpTools) without re-spawning", async () => {
    mockMcpIsAvailable.mockReturnValue(true);
    mockListTools.mockResolvedValue([{ name: "validate_document", description: "Validate" }]);

    // Explicit user action primes the cache (one listTools call).
    await useStore.getState().listMcpTools();
    expect(mockListTools).toHaveBeenCalledOnce();

    useStore.getState().loadBuffer(null, "doc.dita", DOC);
    await useStore.getState().sendChat("hi");

    // sendChat used the cache, not another listTools() spawn.
    expect(mockListTools).toHaveBeenCalledOnce();
    const sentSystem = completeSpy.mock.calls[0][0].system;
    expect(sentSystem).toContain("Available MCP tools");
    expect(sentSystem).toContain("validate_document");
  });
});
