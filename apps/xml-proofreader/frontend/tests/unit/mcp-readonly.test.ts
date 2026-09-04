// Tests for Chunk 27 (D9): the read-only policy is enforced in the store —
// mutating tools are neither advertised (listMcpTools) nor executed
// (approveToolCall), while read-only tools work as before.
//
// store.ts loads adapters via dynamic import(), so the mock factories run lazily.
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { McpPort, McpTool, McpCallResult } from "../../src/ports/McpPort";

const mockMcpIsAvailable = vi.fn<() => boolean>();
const mockListTools = vi.fn<() => Promise<McpTool[]>>();
const mockCallTool = vi.fn<(name: string, args: Record<string, unknown>) => Promise<McpCallResult>>();
vi.mock("../../src/adapters/tauri/TauriMcp", () => ({
  makeTauriMcp: (): McpPort => ({
    isAvailable: mockMcpIsAvailable,
    listTools: mockListTools,
    callTool: mockCallTool,
  }),
}));

const completeSpy = vi.fn<(req: { system: string }) => Promise<string>>();
vi.mock("../../src/adapters/tauri/TauriLlm", () => ({
  makeLlmPortFromSettings: () => ({ isAvailable: () => true, complete: completeSpy }),
}));

import { useStore } from "../../src/ui/store";

function chatHook() {
  return (window as unknown as { __docreview: { __chat: { reset: () => void } } }).__docreview.__chat;
}

beforeEach(() => {
  mockMcpIsAvailable.mockReset().mockReturnValue(true);
  mockListTools.mockReset().mockResolvedValue([]);
  mockCallTool.mockReset().mockResolvedValue({ content: [{ type: "text", text: "ok" }] });
  completeSpy.mockReset();
  chatHook().reset();
  useStore.getState().clearChat(); // reset chatMessages between tests
});

describe("listMcpTools — advertising is read-only", () => {
  it("drops mutating tools from the advertised list", async () => {
    mockListTools.mockResolvedValue([
      { name: "validate_document" },
      { name: "save_file" },
      { name: "check_links" },
      { name: "delete_node" },
    ]);
    const tools = await useStore.getState().listMcpTools();
    expect(tools.map((t) => t.name)).toEqual(["validate_document", "check_links"]);
  });
});

describe("approveToolCall — execution is read-only", () => {
  async function proposeTool(tool: string) {
    completeSpy.mockResolvedValue(`<tool_call>{"tool":"${tool}","args":{}}</tool_call>`);
    await useStore.getState().sendChat("do it");
    const msg = useStore.getState().chatMessages.find((m) => m.role === "assistant")!;
    return { messageId: msg.id, call: msg.toolCalls[0] };
  }

  it("blocks a mutating tool: callTool is NOT invoked and the call is rejected", async () => {
    const { messageId, call } = await proposeTool("delete_node");
    await useStore.getState().approveToolCall(messageId, call.id);

    expect(mockCallTool).not.toHaveBeenCalled();
    const msg = useStore.getState().chatMessages.find((m) => m.id === messageId)!;
    const tc = msg.toolCalls[0];
    expect(tc.status).toBe("rejected");
    expect(tc.error).toMatch(/read-only/i);
  });

  it("executes a read-only tool normally", async () => {
    const { messageId, call } = await proposeTool("validate_document");
    await useStore.getState().approveToolCall(messageId, call.id);

    expect(mockCallTool).toHaveBeenCalledOnce();
    expect(mockCallTool).toHaveBeenCalledWith("validate_document", {});
    const msg = useStore.getState().chatMessages.find((m) => m.id === messageId)!;
    expect(msg.toolCalls[0].result).toBe("ok");
  });
});
