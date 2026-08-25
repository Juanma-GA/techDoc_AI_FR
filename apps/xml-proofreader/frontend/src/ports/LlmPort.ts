// Provider-agnostic LLM port (ADR-0008).
// core/ depends only on this interface; adapters (Tauri) implement it.

export interface LlmRequest {
  system: string;
  content: string;
  /** Model identifier as understood by the active provider. */
  model: string;
  maxTokens?: number;
  /** Request a JSON object as the sole output. */
  jsonMode?: boolean;
}

export interface LlmPort {
  /** Returns the text completion produced by the model. Throws on error. */
  complete(req: LlmRequest): Promise<string>;
  /**
   * Streams a completion (ADR-0022): `onDelta` is called with each text chunk as
   * it arrives, and the promise resolves with the **full** text (authoritative —
   * a caller may rely on it even if a trailing delta was missed). Throws on error
   * so the caller can fall back to {@link complete}. Optional: adapters that
   * cannot stream (browser, test mocks) omit it and callers fall back to
   * `complete`.
   */
  completeStream?(req: LlmRequest, onDelta: (delta: string) => void): Promise<string>;
  /** False in browser / when no provider is configured. */
  isAvailable(): boolean;
}
