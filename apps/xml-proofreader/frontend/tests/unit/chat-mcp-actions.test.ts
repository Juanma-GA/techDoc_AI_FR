// Tests for Chunk 14 (C5): curated action chips + listMcpTools store action.
//
// Strategy:
//   • CURATED_ACTIONS (pure data) — shape and invariants, no mocking needed.
//   • listMcpTools (store action) — intercept the TauriMcp dynamic import (same
//     pattern as chat.test.ts) and assert behaviour.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CURATED_ACTIONS } from "../../src/ui/chat/actions";
import { useStore } from "../../src/ui/store";
import type { McpPort, McpTool } from "../../src/ports/McpPort";

// ── TauriMcp mock (hoisted, same pattern as chat.test.ts) ────────────────────
const mockListTools = vi.fn<() => Promise<McpTool[]>>();
const mockIsAvailable = vi.fn<() => boolean>().mockReturnValue(false);

vi.mock("../../src/adapters/tauri/TauriMcp", () => ({
  makeTauriMcp: (): McpPort => ({
    isAvailable: mockIsAvailable,
    listTools: mockListTools,
    callTool: vi.fn(),
  }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function resetMocks() {
  mockIsAvailable.mockReturnValue(false);
  mockListTools.mockReset();
}

// ── CURATED_ACTIONS shape ─────────────────────────────────────────────────────

describe("CURATED_ACTIONS", () => {
  it("has at least 3 entries", () => {
    expect(CURATED_ACTIONS.length).toBeGreaterThanOrEqual(3);
  });

  it("every entry has a non-empty label and prompt", () => {
    for (const a of CURATED_ACTIONS) {
      expect(typeof a.label).toBe("string");
      expect(a.label.length).toBeGreaterThan(0);
      expect(typeof a.prompt).toBe("string");
      expect(a.prompt.length).toBeGreaterThan(0);
    }
  });

  it("first entry is 'Run Oxygen check'", () => {
    expect(CURATED_ACTIONS[0].label).toContain("Oxygen");
  });

  it("prompts are distinct", () => {
    const prompts = CURATED_ACTIONS.map((a) => a.prompt);
    const unique = new Set(prompts);
    expect(unique.size).toBe(prompts.length);
  });
});

// ── listMcpTools store action ─────────────────────────────────────────────────

describe("listMcpTools", () => {
  beforeEach(resetMocks);

  it("throws when MCP is not available", async () => {
    mockIsAvailable.mockReturnValue(false);
    await expect(useStore.getState().listMcpTools()).rejects.toThrow(/not configured/i);
    expect(mockListTools).not.toHaveBeenCalled();
  });

  it("returns tools when MCP is available", async () => {
    mockIsAvailable.mockReturnValue(true);
    const fakeTools: McpTool[] = [
      { name: "validate_document", description: "Validates the document" },
      { name: "check_links", description: "Checks all hyperlinks" },
    ];
    mockListTools.mockResolvedValue(fakeTools);

    const result = await useStore.getState().listMcpTools();

    expect(mockListTools).toHaveBeenCalledOnce();
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("validate_document");
    expect(result[1].name).toBe("check_links");
  });

  it("propagates errors from listTools", async () => {
    mockIsAvailable.mockReturnValue(true);
    mockListTools.mockRejectedValue(new Error("Oxygen not running"));

    await expect(useStore.getState().listMcpTools()).rejects.toThrow("Oxygen not running");
  });

  it("returns empty array when listTools returns empty", async () => {
    mockIsAvailable.mockReturnValue(true);
    mockListTools.mockResolvedValue([]);

    const result = await useStore.getState().listMcpTools();
    expect(result).toEqual([]);
  });
});
