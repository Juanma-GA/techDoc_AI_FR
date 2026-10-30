export type SseEventHandler = (event: string, data: Record<string, unknown>) => void;

function isEventData(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

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
      if (!isEventData(parsed)) throw new Error("Invalid SSE event payload.");
      onEvent(event, parsed);
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
