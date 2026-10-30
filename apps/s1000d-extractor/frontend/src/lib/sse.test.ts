import { describe, expect, it, vi } from "vitest";

import { readSse } from "./sse";

function response(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }));
}

describe("shared SSE reader", () => {
  it("parses split events, CRLF and multi-line data", async () => {
    const handler = vi.fn();
    await readSse(response([
      "event: sess", "ion\r", '\ndata: {"document_id":\r\n',
      'data: "synthetic"}\r\n\r', "\nevent: progress\r\ndata:",
      ' {"pct":50}\r\n\r\nevent: done\r\ndata: {"ok":true}',
    ]), handler);
    expect(handler.mock.calls).toEqual([
      ["session", { document_id: "synthetic" }],
      ["progress", { pct: 50 }],
      ["done", { ok: true }],
    ]);
  });

  it("processes an unterminated final block", async () => {
    const handler = vi.fn();
    await readSse(response(['event: done\ndata: {"value":"final"}']), handler);
    expect(handler).toHaveBeenCalledWith("done", { value: "final" });
  });

  it("rejects malformed payloads instead of reporting an empty success", async () => {
    await expect(readSse(response(["event: done\ndata: broken\n\n"]), vi.fn())).rejects.toThrow();
    await expect(readSse(response(["event: done\ndata: []\n\n"]), vi.fn())).rejects.toThrow(
      "Invalid SSE event payload",
    );
  });

  it("cancels a quiet stream when aborted", async () => {
    const cancelled = vi.fn();
    const controller = new AbortController();
    const stream = new ReadableStream<Uint8Array>({ cancel: cancelled });
    const reading = readSse(new Response(stream), vi.fn(), controller.signal);
    controller.abort();
    await expect(reading).rejects.toMatchObject({ name: "AbortError" });
    expect(cancelled).toHaveBeenCalledOnce();
    expect(stream.locked).toBe(false);
  });
});
