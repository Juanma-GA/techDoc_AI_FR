// F4 (ADR-0029): directInvokeTool — creates a pending ToolCallProposal without
// an LLM round-trip and switches the panel to "chat".
import { describe, it, expect, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";
import type { McpTool } from "../../src/ports/McpPort";

// The __docreview seam is registered in store.ts only when window is defined.
// jsdom provides window, so the seam is available in this environment.

function getDocreview() {
  return (window as unknown as { __docreview: {
    __chat: {
      enable: () => void;
      reset: () => void;
      setMcpCache: (endpoint: string, tools: McpTool[]) => void;
    };
  } }).__docreview;
}

const TOOL: McpTool = {
  name: "get_document_info",
  description: "Returns metadata about the active document",
  inputSchema: {
    type: "object",
    properties: { format: { type: "string" } },
    required: [],
  },
};

beforeEach(() => {
  getDocreview().__chat.reset();
  useStore.setState({ chatMessages: [], chatPending: false, chatAvailable: true, rightMode: "comments" });
});

describe("directInvokeTool — F4", () => {
  it("adds a pending ToolCallProposal for the named tool", () => {
    getDocreview().__chat.setMcpCache("stdio://oxygen-xml", [TOOL]);

    useStore.getState().directInvokeTool("get_document_info");

    const msgs = useStore.getState().chatMessages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].role).toBe("assistant");
    expect(msgs[0].toolCalls).toHaveLength(1);
    const tc = msgs[0].toolCalls[0];
    expect(tc.toolName).toBe("get_document_info");
    expect(tc.status).toBe("pending");
  });

  it("switches rightMode to 'chat'", () => {
    getDocreview().__chat.setMcpCache("stdio://oxygen-xml", [TOOL]);

    useStore.getState().directInvokeTool("get_document_info");

    expect(useStore.getState().rightMode).toBe("chat");
  });

  it("is a no-op when the tool is not in the cache (returns, does not throw)", () => {
    // Cache empty — directInvokeTool for an unknown tool should not crash.
    // It still creates a proposal with empty args (graceful degradation).
    getDocreview().__chat.setMcpCache("stdio://oxygen-xml", []);

    expect(() => useStore.getState().directInvokeTool("nonexistent_tool")).not.toThrow();
    // A message with a pending proposal is still created (toolName is preserved).
    const msgs = useStore.getState().chatMessages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].toolCalls[0].toolName).toBe("nonexistent_tool");
    expect(msgs[0].toolCalls[0].status).toBe("pending");
  });

  it("proposal args are coerced from an empty object (no schema defaults crash)", () => {
    getDocreview().__chat.setMcpCache("stdio://oxygen-xml", [TOOL]);

    useStore.getState().directInvokeTool("get_document_info");

    const tc = useStore.getState().chatMessages[0].toolCalls[0];
    expect(typeof tc.args).toBe("object");
    expect(tc.args).not.toBeNull();
  });
});
