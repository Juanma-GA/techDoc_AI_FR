// Guard test: verifies that TauriLlm and TauriMcp send camelCase argument keys
// to `invoke`, matching what Tauri 2 expects (it deserializes camelCase → snake_case
// on the Rust side automatically). Regression guard for C1 (Chunk 11).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { makeTauriMcp } from "../../src/adapters/tauri/TauriMcp";
import { makeAnthropicProvider, makeOpenAICompatProvider } from "../../src/adapters/tauri/TauriLlm";

// ---------------------------------------------------------------------------
// Bridge mock helpers
// ---------------------------------------------------------------------------

let capturedArgs: Record<string, unknown> = {};
let capturedCmd = "";

function installBridgeMock(returnValue: unknown = "") {
  const invoke = vi.fn(async (cmd: string, args?: Record<string, unknown>) => {
    capturedCmd = cmd;
    capturedArgs = args ?? {};
    return returnValue;
  });
  (globalThis as unknown as Record<string, unknown>).__TAURI__ = { core: { invoke } };
  return invoke;
}

function removeBridgeMock() {
  delete (globalThis as unknown as Record<string, unknown>).__TAURI__;
}

beforeEach(() => { capturedArgs = {}; capturedCmd = ""; });
afterEach(() => removeBridgeMock());

// ---------------------------------------------------------------------------
// TauriLlm — llm_complete args must be camelCase
// ---------------------------------------------------------------------------

describe("TauriLlm — invoke arg keys", () => {
  it("makeAnthropicProvider sends apiKey, maxTokens, jsonMode (no snake_case)", async () => {
    installBridgeMock("result");
    const port = makeAnthropicProvider(() => "test-key");
    await port.complete({ system: "sys", content: "hi", model: "claude-sonnet-4-6", maxTokens: 1024, jsonMode: false });
    expect(capturedCmd).toBe("llm_complete");
    expect(capturedArgs).toHaveProperty("apiKey", "test-key");
    expect(capturedArgs).toHaveProperty("maxTokens", 1024);
    expect(capturedArgs).toHaveProperty("jsonMode", false);
    expect(capturedArgs).not.toHaveProperty("api_key");
    expect(capturedArgs).not.toHaveProperty("max_tokens");
    expect(capturedArgs).not.toHaveProperty("json_mode");
  });

  it("makeOpenAICompatProvider sends baseUrl instead of base_url", async () => {
    installBridgeMock("result");
    const port = makeOpenAICompatProvider(() => "https://api.mistral.ai/v1", () => "key");
    await port.complete({ system: "sys", content: "hi", model: "mistral-medium-latest" });
    expect(capturedArgs).toHaveProperty("baseUrl", "https://api.mistral.ai/v1");
    expect(capturedArgs).not.toHaveProperty("base_url");
  });
});

// ---------------------------------------------------------------------------
// TauriMcp — mcp_stdio_call args must be camelCase
// ---------------------------------------------------------------------------

describe("TauriMcp — mcp_stdio_call invoke arg keys", () => {
  it("sends exePath instead of exe_path for stdio transport", async () => {
    installBridgeMock({ tools: [] });
    const mcp = makeTauriMcp(() => "/opt/oxygen/oxygen.sh");
    await mcp.listTools();
    expect(capturedCmd).toBe("mcp_stdio_call");
    expect(capturedArgs).toHaveProperty("exePath", "/opt/oxygen/oxygen.sh");
    expect(capturedArgs).not.toHaveProperty("exe_path");
  });

  it("uses mcp_call (not mcp_stdio_call) for HTTP endpoints", async () => {
    installBridgeMock({ tools: [] });
    const mcp = makeTauriMcp(() => "http://localhost:7071");
    await mcp.listTools();
    expect(capturedCmd).toBe("mcp_call");
    expect(capturedArgs).toHaveProperty("endpoint", "http://localhost:7071");
  });
});
