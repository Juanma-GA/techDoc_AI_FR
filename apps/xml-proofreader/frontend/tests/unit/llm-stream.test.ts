// Streaming LLM transport (E4 / ADR-0022).
//   1. TauriLlm.completeStream: forwards each delta from the per-call Tauri
//      event channel and resolves with the command's full text; the listener is
//      always torn down.
//   2. store.sendChat: builds the assistant bubble incrementally from deltas and
//      finalizes with parsed <tool_call> tags.
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { makeOpenAICompatProvider } from "../../src/adapters/tauri/TauriLlm";
import { useStore } from "../../src/ui/store";

type Handler = (e: { payload: string }) => void;
type DocReview = {
  __docreview: { __chat: { mockStream: (r: string, chunks?: number) => void; reset: () => void } };
};

// ── 1. TauriLlm.completeStream (mocked event channel) ──────────────────────────

describe("TauriLlm.completeStream", () => {
  let handler: Handler | null = null;
  let unlisten: ReturnType<typeof vi.fn>;
  let invoke: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    handler = null;
    unlisten = vi.fn();
    // Fake Rust command: emit deltas through the captured listener, then resolve
    // with the full (authoritative) text.
    invoke = vi.fn(async () => {
      for (const d of ["Hel", "lo, ", "world"]) handler?.({ payload: d });
      return "Hello, world";
    });
    (window as unknown as { __TAURI__: unknown }).__TAURI__ = {
      core: { invoke },
      event: {
        listen: vi.fn(async (_name: string, h: Handler) => {
          handler = h;
          return unlisten;
        }),
      },
    };
  });

  afterEach(() => {
    delete (window as unknown as { __TAURI__?: unknown }).__TAURI__;
  });

  it("forwards each delta and resolves with the full text", async () => {
    const provider = makeOpenAICompatProvider(() => "https://api.example/v1", () => "key");
    const seen: string[] = [];
    const full = await provider.completeStream!(
      { system: "s", content: "c", model: "m" },
      (d) => seen.push(d)
    );
    expect(seen).toEqual(["Hel", "lo, ", "world"]);
    expect(full).toBe("Hello, world");
    expect(unlisten).toHaveBeenCalledOnce();
  });

  it("tears down the listener even when the command rejects", async () => {
    invoke.mockRejectedValueOnce(new Error("boom"));
    const provider = makeOpenAICompatProvider(() => "https://api.example/v1", () => "key");
    await expect(
      provider.completeStream!({ system: "s", content: "c", model: "m" }, () => {})
    ).rejects.toThrow("boom");
    expect(unlisten).toHaveBeenCalledOnce();
  });

  it("passes streamId and request fields to the command", async () => {
    const provider = makeOpenAICompatProvider(() => "https://api.example/v1", () => "key");
    await provider.completeStream!(
      { system: "sys", content: "msg", model: "mistral", maxTokens: 123 },
      () => {}
    );
    expect(invoke).toHaveBeenCalledWith(
      "llm_complete_stream",
      expect.objectContaining({
        provider: "openai-compat",
        model: "mistral",
        system: "sys",
        content: "msg",
        maxTokens: 123,
        streamId: expect.any(String),
      })
    );
  });
});

// ── 2. store.sendChat streaming path ───────────────────────────────────────────

function chatSeam() {
  return (window as unknown as DocReview).__docreview.__chat;
}

describe("sendChat — streaming", () => {
  beforeEach(() => {
    useStore.getState().clearChat();
    chatSeam().reset();
    useStore.setState({ chatAvailable: true });
    useStore.getState().loadBuffer(null, "t.dita", "<topic><title>T</title><body/></topic>");
  });

  it("builds the assistant message incrementally and finalizes with the full text", async () => {
    chatSeam().mockStream("Hello from the stream", 4);

    await useStore.getState().sendChat("Hi");

    const msgs = useStore.getState().chatMessages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].role).toBe("user");
    expect(msgs[1].role).toBe("assistant");
    expect(msgs[1].text).toBe("Hello from the stream");
    expect(useStore.getState().chatPending).toBe(false);
  });

  it("parses <tool_call> tags from the streamed text and strips them from display", async () => {
    const raw = 'Checking.\n<tool_call>{"tool":"validate_doc","args":{"x":1}}</tool_call>\nDone.';
    chatSeam().mockStream(raw, 5);

    await useStore.getState().sendChat("Validate");

    const assistant = useStore.getState().chatMessages.find((m) => m.role === "assistant")!;
    expect(assistant.text).not.toContain("<tool_call>");
    expect(assistant.toolCalls).toHaveLength(1);
    expect(assistant.toolCalls[0].toolName).toBe("validate_doc");
    expect(assistant.toolCalls[0].args).toEqual({ x: 1 });
    expect(assistant.toolCalls[0].status).toBe("pending");
  });
});
