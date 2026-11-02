import { ApiRequestError, responseId } from "./client";
import { z } from "zod";

const sessionDataSchema = z.record(z.unknown()).superRefine((data, context) => {
  if (typeof data.document_id !== "string" || !data.document_id) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["document_id"], message: "Invalid session event." });
  }
});
const progressDataSchema = z.record(z.unknown()).superRefine((data, context) => {
  if (typeof data.step !== "string" || !data.step) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["step"], message: "Invalid progress step." });
  }
  if (
    typeof data.pct !== "number" ||
    !Number.isInteger(data.pct) ||
    data.pct < 0 ||
    data.pct > 100
  ) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["pct"], message: "Invalid progress percentage." });
  }
});
const errorDataSchema = z.record(z.unknown()).superRefine((data, context) => {
  if (typeof data.code !== "string" || !data.code) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["code"], message: "Invalid stream error code." });
  }
  if (typeof data.message !== "string" || !data.message) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["message"], message: "Invalid stream error message." });
  }
});

export const sseEventSchema = z.discriminatedUnion("event", [
  z.object({ event: z.literal("session"), data: sessionDataSchema }),
  z.object({ event: z.literal("progress"), data: progressDataSchema }),
  z.object({ event: z.literal("done"), data: z.record(z.unknown()) }),
  z.object({ event: z.literal("error"), data: errorDataSchema }),
]);

export type SseEventHandler = (event: string, data: Record<string, unknown>) => void;

async function closeReader(reader: ReadableStreamDefaultReader<Uint8Array>, signal?: AbortSignal) {
  try {
    await reader.cancel(signal?.reason);
  } catch (error) {
    if (!(signal?.aborted && error instanceof DOMException && error.name === "AbortError")) throw error;
  } finally {
    reader.releaseLock();
  }
}

export async function readSse(
  response: Response,
  onEvent: SseEventHandler,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
  signal?.throwIfAborted();
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "message";
  let data: string[] = [];
  const dispatch = () => {
    if (data.length) {
      const parsed: unknown = JSON.parse(data.join("\n"));
      const validated = sseEventSchema.parse({ event, data: parsed });
      onEvent(validated.event, validated.data);
    }

    data = [];
    event = "message";
  };
  const line = (value: string) => {
    const text = value.endsWith("\r") ? value.slice(0, -1) : value;
    if (text === "") dispatch();
    else if (text.startsWith("event:")) event = text.slice(6).replace(/^ /, "");
    else if (text.startsWith("data:")) data.push(text.slice(5).replace(/^ /, ""));
  };
  let abortListener: (() => void) | undefined;
  const aborted = signal ? new Promise<never>((_resolve, reject) => {
    abortListener = () => reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", abortListener, { once: true });
  }) : undefined;
  try {
    for (;;) {
      const result = await (aborted ? Promise.race([reader.read(), aborted]) : reader.read());
      signal?.throwIfAborted();
      buffer += decoder.decode(result.value, { stream: !result.done });
      let end: number;
      while ((end = buffer.indexOf("\n")) !== -1) {
        line(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
      }
      if (result.done) break;
    }
    if (buffer) line(buffer);
    dispatch();
  } finally {
    if (abortListener) signal?.removeEventListener("abort", abortListener);
    await closeReader(reader, signal);
  }
}

export async function readApiSse(response: Response, onEvent: SseEventHandler, signal?: AbortSignal) {
  try {
    await readSse(response, onEvent, signal);
  } catch (error) {
    if (error instanceof ApiRequestError || signal?.aborted) throw error;
    throw new ApiRequestError(response.status, "INVALID_STREAM",
      error instanceof Error ? error.message : String(error), responseId(response));
  }
}
