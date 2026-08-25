// Unit tests for AI Chat store actions (Chunk 8 / B8c).
//
// Key invariant: rejectToolCall MUST NOT call MCP. Only approveToolCall may.
// MCP is intercepted via vi.mock on TauriMcp so every dynamic import of that
// module returns our controlled spy instead of the real Tauri adapter.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";
import type { McpPort, McpTool } from "../../src/ports/McpPort";

// ── MCP mock ─────────────────────────────────────────────────────────────────
// We intercept the dynamic import that store.ts does at call time:
//   const { makeTauriMcp } = await import("../adapters/tauri/TauriMcp");
// Vitest hoists vi.mock calls, so this mock is in effect for all tests.

const mockCallTool = vi.fn<McpPort["callTool"]>();
const mockListTools = vi.fn<() => Promise<McpTool[]>>();
const mockIsAvailable = vi.fn<() => boolean>().mockReturnValue(false);

vi.mock("../../src/adapters/tauri/TauriMcp", () => ({
  makeTauriMcp: () => ({
    isAvailable: mockIsAvailable,
    listTools: mockListTools,
    callTool: mockCallTool,
  }),
}));

// ── seam helpers ──────────────────────────────────────────────────────────────

type ChatSeam = { mock: (r: string) => void; reset: () => void; enable: () => void };
type DocReview = { __docreview: { __chat: ChatSeam } };

function chatSeam(): ChatSeam {
  return (window as unknown as DocReview).__docreview.__chat;
}

function resetChat() {
  useStore.getState().clearChat();
  chatSeam().reset();
  useStore.setState({ chatAvailable: true });
  mockCallTool.mockReset();
  mockListTools.mockReset();
  mockIsAvailable.mockReturnValue(false);
}

// ── clearChat ─────────────────────────────────────────────────────────────────

describe("clearChat", () => {
  beforeEach(resetChat);

  it("resets messages and pending flag", () => {
    useStore.setState({
      chatMessages: [{ id: "1", role: "user", text: "hi", toolCalls: [], timestamp: 0 }],
      chatPending: true,
    });
    useStore.getState().clearChat();
    const s = useStore.getState();
    expect(s.chatMessages).toHaveLength(0);
    expect(s.chatPending).toBe(false);
  });
});

// ── rejectToolCall ────────────────────────────────────────────────────────────

describe("rejectToolCall", () => {
  beforeEach(resetChat);

  it("marks the tool call as rejected and NEVER calls MCP callTool", () => {
    const callId = "tc-1";
    const msgId = "msg-1";
    useStore.setState({
      chatMessages: [
        {
          id: msgId,
          role: "assistant",
          text: "I can validate this for you.",
          toolCalls: [{ id: callId, toolName: "validate_doc", args: {}, status: "pending" }],
          timestamp: Date.now(),
        },
      ],
    });

    useStore.getState().rejectToolCall(msgId, callId);

    const tc = useStore
      .getState()
      .chatMessages.find((m) => m.id === msgId)
      ?.toolCalls.find((c) => c.id === callId);
    expect(tc?.status).toBe("rejected");
    // The MCP spy must never have been reached.
    expect(mockCallTool).not.toHaveBeenCalled();
  });

  it("does not affect other tool calls or messages", () => {
    const msgId = "msg-2";
    const other = "tc-other";
    const target = "tc-target";
    useStore.setState({
      chatMessages: [
        {
          id: msgId,
          role: "assistant",
          text: "",
          toolCalls: [
            { id: target, toolName: "run_check", args: {}, status: "pending" },
            { id: other, toolName: "list_tools", args: {}, status: "pending" },
          ],
          timestamp: Date.now(),
        },
      ],
    });

    useStore.getState().rejectToolCall(msgId, target);

    const tcs = useStore.getState().chatMessages.find((m) => m.id === msgId)?.toolCalls ?? [];
    expect(tcs.find((c) => c.id === target)?.status).toBe("rejected");
    expect(tcs.find((c) => c.id === other)?.status).toBe("pending");
  });
});

// ── sendChat ──────────────────────────────────────────────────────────────────

describe("sendChat", () => {
  beforeEach(() => {
    resetChat();
    useStore.getState().loadBuffer(null, "test.dita", "<topic><title>T</title><body/></topic>");
  });

  it("adds user message and then assistant message", async () => {
    chatSeam().mock("Hello from AI");

    await useStore.getState().sendChat("Tell me about this doc");

    const msgs = useStore.getState().chatMessages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].role).toBe("user");
    expect(msgs[0].text).toBe("Tell me about this doc");
    expect(msgs[1].role).toBe("assistant");
    expect(msgs[1].text).toBe("Hello from AI");
    expect(useStore.getState().chatPending).toBe(false);
  });

  it("parses <tool_call> tags into toolCalls and strips them from display text", async () => {
    const raw =
      'I can check this.\n<tool_call>{"tool":"validate_doc","args":{"strictness":"high"}}</tool_call>\nLet me know.';
    chatSeam().mock(raw);

    await useStore.getState().sendChat("Validate please");

    const assistant = useStore.getState().chatMessages.find((m) => m.role === "assistant")!;
    expect(assistant.text).not.toContain("<tool_call>");
    expect(assistant.toolCalls).toHaveLength(1);
    expect(assistant.toolCalls[0].toolName).toBe("validate_doc");
    expect(assistant.toolCalls[0].args).toEqual({ strictness: "high" });
    expect(assistant.toolCalls[0].status).toBe("pending");
    // Proposals must remain pending — sendChat must NOT auto-call MCP.
    expect(mockCallTool).not.toHaveBeenCalled();
  });

  it("sets chatPending=false on LLM error and appends error assistant message", async () => {
    chatSeam().reset();
    // No mock → makeLlmPortFromSettings runs in the test env where Tauri commands
    // are absent, so complete() will throw. Exercises the catch branch.
    const before = useStore.getState().chatMessages.length;

    await useStore.getState().sendChat("This will error");

    const msgs = useStore.getState().chatMessages;
    expect(msgs.length).toBeGreaterThan(before);
    expect(msgs[msgs.length - 1].role).toBe("assistant");
    expect(msgs[msgs.length - 1].text).toMatch(/error/i);
    expect(useStore.getState().chatPending).toBe(false);
  });
});

// ── approveToolCall ───────────────────────────────────────────────────────────

describe("approveToolCall", () => {
  beforeEach(resetChat);

  it("calls MCP callTool with (toolName, args) and stores result in the tool call", async () => {
    mockIsAvailable.mockReturnValue(true);
    mockCallTool.mockResolvedValue({
      content: [{ type: "text", text: "Validation OK: 0 errors" }],
    });

    const msgId = "msg-approve";
    const callId = "tc-approve";
    useStore.setState({
      chatMessages: [
        {
          id: msgId,
          role: "assistant",
          text: "Let me validate.",
          toolCalls: [
            {
              id: callId,
              toolName: "validate_doc",
              args: { strictness: "high" },
              status: "pending",
            },
          ],
          timestamp: Date.now(),
        },
      ],
    });

    await useStore.getState().approveToolCall(msgId, callId);

    expect(mockCallTool).toHaveBeenCalledOnce();
    expect(mockCallTool).toHaveBeenCalledWith("validate_doc", { strictness: "high" });

    const tc = useStore
      .getState()
      .chatMessages.find((m) => m.id === msgId)
      ?.toolCalls.find((c) => c.id === callId);
    expect(tc?.status).toBe("approved");
    expect(tc?.result).toBe("Validation OK: 0 errors");
    expect(tc?.error).toBeUndefined();
  });

  it("stores the error when callTool throws and marks status approved", async () => {
    mockIsAvailable.mockReturnValue(true);
    mockCallTool.mockRejectedValue(new Error("MCP timeout"));

    const msgId = "msg-err";
    const callId = "tc-err";
    useStore.setState({
      chatMessages: [
        {
          id: msgId,
          role: "assistant",
          text: "",
          toolCalls: [{ id: callId, toolName: "run_check", args: {}, status: "pending" }],
          timestamp: Date.now(),
        },
      ],
    });

    await useStore.getState().approveToolCall(msgId, callId);

    const tc = useStore
      .getState()
      .chatMessages.find((m) => m.id === msgId)
      ?.toolCalls.find((c) => c.id === callId);
    expect(tc?.status).toBe("approved");
    expect(tc?.error).toMatch(/MCP timeout/);
  });
});
