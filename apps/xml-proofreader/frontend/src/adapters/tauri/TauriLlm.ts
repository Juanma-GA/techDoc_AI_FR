// LlmPort adapters for Tauri. Transport is handled in Rust (ADR-0008).
// Two providers: "anthropic" (Messages API) and "openai-compat" (Chat Completions).
// Uses the window.__TAURI__ bridge (no compile-time @tauri-apps/api dep — same
// pattern as TauriFileSystem.ts so the browser bundle stays clean).

import type { LlmPort, LlmRequest } from "../../ports/LlmPort";

interface TauriBridge {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
  event: {
    listen<T>(event: string, handler: (e: { payload: T }) => void): Promise<() => void>;
  };
}

function bridge(): TauriBridge {
  const t = (window as unknown as { __TAURI__?: TauriBridge }).__TAURI__;
  if (!t) throw new Error("Tauri bridge unavailable");
  return t;
}

function makeTauriProvider(
  provider: "anthropic" | "openai-compat",
  getBaseUrl: () => string | null,
  getApiKey: () => string,
  available: () => boolean
): LlmPort {
  return {
    isAvailable: available,
    async complete(req: LlmRequest): Promise<string> {
      return await bridge().core.invoke<string>("llm_complete", {
        provider,
        baseUrl: getBaseUrl(),
        model: req.model,
        apiKey: getApiKey(),
        system: req.system,
        content: req.content,
        maxTokens: req.maxTokens ?? 2048,
        jsonMode: req.jsonMode ?? false,
      });
    },
    // ADR-0022: stream the completion. We subscribe to a per-call Tauri event
    // (isolated by a random stream id), forward each delta to onDelta, and let
    // the command's return value be the authoritative full text. The listener is
    // always torn down in `finally` so we never leak subscriptions.
    async completeStream(req: LlmRequest, onDelta: (delta: string) => void): Promise<string> {
      const b = bridge();
      const streamId = crypto.randomUUID();
      const eventName = `llm-stream:${streamId}`;
      let unlisten: (() => void) | null = null;
      try {
        unlisten = await b.event.listen<string>(eventName, (e) => {
          if (e.payload) onDelta(e.payload);
        });
        return await b.core.invoke<string>("llm_complete_stream", {
          provider,
          baseUrl: getBaseUrl(),
          model: req.model,
          apiKey: getApiKey(),
          system: req.system,
          content: req.content,
          maxTokens: req.maxTokens ?? 2048,
          streamId,
        });
      } finally {
        if (unlisten) unlisten();
      }
    },
  };
}

/**
 * Creates a LlmPort backed by the Anthropic Messages API.
 * The key is read lazily so Settings changes are picked up without re-creation.
 */
export function makeAnthropicProvider(
  getApiKey: () => string,
  available: () => boolean = () => true
): LlmPort {
  return makeTauriProvider("anthropic", () => null, getApiKey, available);
}

/**
 * Creates a LlmPort backed by an OpenAI-compatible Chat Completions endpoint
 * (covers Mistral, OpenAI, and self-hosted endpoints).
 */
export function makeOpenAICompatProvider(
  getBaseUrl: () => string,
  getApiKey: () => string,
  available: () => boolean = () => true
): LlmPort {
  return makeTauriProvider("openai-compat", getBaseUrl, getApiKey, available);
}

/**
 * Returns the appropriate LlmPort based on the current Settings provider field.
 * Falls back to a no-op unavailable port in the browser.
 */
export function makeLlmPortFromSettings(settings: {
  provider: "anthropic" | "openai-compat";
  base_url?: string;
  apiKey: string;
}): LlmPort {
  if (settings.provider === "openai-compat") {
    return makeOpenAICompatProvider(
      () => settings.base_url ?? "https://api.mistral.ai/v1",
      () => settings.apiKey
    );
  }
  return makeAnthropicProvider(() => settings.apiKey);
}
