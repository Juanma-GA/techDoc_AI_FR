/**
 * LLM API client — proxies to the BRDP Manager backend (`/api/v1/llm/*`), which
 * holds the Mistral API key server-side (STANDARD_POC.md rule #6). Single
 * provider (Mistral) — the `apiKey` / `provider` / `customEndpoint` params kept
 * in these signatures are ignored, for source-compatibility with the callers
 * (generateBREX*.js, extractBRDPs.js) which still pass them.
 */

const CHAT_ENDPOINT = "/api/v1/llm/chat";
const CHAT_STREAM_ENDPOINT = "/api/v1/llm/chat/stream";

/**
 * Send a message to the backend LLM proxy (non-streaming).
 * @param {Array} messages - Message history ([{role, content}])
 * @param {string} _apiKey - Unused (key is server-side now)
 * @param {string} _modelName - Unused (model is server-configured)
 * @param {string} _provider - Unused (Mistral only)
 * @param {string} [systemPrompt=""] - System prompt
 * @param {Object} [options={}]
 * @param {number} [options.temperature=1]
 * @returns {Promise<{role: string, content: string}>}
 */
export async function sendMessage(
  messages,
  _apiKey,
  _modelName,
  _provider,
  systemPrompt = "",
  options = {}
) {
  const { temperature = 1 } = options;

  const response = await fetch(CHAT_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, system: systemPrompt, temperature }),
  });

  if (!response.ok) {
    throw new Error("Connection error. Please try again.");
  }

  const data = await response.json();
  if (data.skipped) {
    throw new Error(data.content || "LLM unavailable. Please check Settings.");
  }

  return { role: "assistant", content: data.content };
}

/**
 * Stream a message from the backend LLM proxy (SSE).
 * @param {Array} messages - Message history
 * @param {string} _apiKey - Unused
 * @param {string} _modelName - Unused
 * @param {string} _provider - Unused
 * @param {string} [systemPrompt=""] - System prompt
 * @param {Function} onChunk - Callback for each token received
 * @param {AbortController} abortController - Controller to cancel request
 * @param {Object} [options={}]
 * @param {number} [options.temperature=1]
 * @returns {Promise<string>} Complete response text
 */
export async function sendMessageStream(
  messages,
  _apiKey,
  _modelName,
  _provider,
  systemPrompt = "",
  onChunk,
  abortController,
  options = {}
) {
  const { temperature = 1 } = options;

  const response = await fetch(CHAT_STREAM_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, system: systemPrompt, temperature }),
    signal: abortController?.signal,
  });

  if (!response.ok) {
    throw new Error("Connection error. Please try again.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let fullContent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === "[DONE]") continue;

      let obj;
      try {
        obj = JSON.parse(raw);
      } catch {
        continue;
      }

      if (obj.error) {
        throw new Error(obj.error);
      }
      if (obj.delta) {
        fullContent += obj.delta;
        onChunk?.(obj.delta);
      }
    }
  }

  return fullContent;
}
