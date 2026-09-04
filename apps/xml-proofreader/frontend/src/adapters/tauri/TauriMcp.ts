// MCP client adapter for Tauri. Transport is handled in Rust (ADR-0002).
// Two transports supported by the Rust side:
//   • Streamable HTTP  — endpoint is an http:// or https:// URL → mcp_call
//   • Stdio            — endpoint is a file path to oxygen.bat/oxygen.sh → mcp_stdio_call
//
// A bare `stdio://oxygen-xml-28` placeholder means "not yet configured" and
// makes isAvailable() return false without throwing.
//
// Uses the window.__TAURI__ bridge — no compile-time @tauri-apps/api dep
// (same pattern as TauriLlm.ts so the browser bundle stays clean).

import type { McpPort, McpTool, McpCallResult } from "../../ports/McpPort";

interface TauriBridge {
  core: { invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> };
}

function bridge(): TauriBridge {
  const t = (window as unknown as { __TAURI__?: TauriBridge }).__TAURI__;
  if (!t) throw new Error("Tauri bridge unavailable");
  return t;
}

function tauriAvailable(): boolean {
  // Guard `window` so this never throws in a non-browser (node/test) context.
  return typeof window !== "undefined"
    && !!(window as unknown as { __TAURI__?: unknown }).__TAURI__;
}

/**
 * True when the endpoint string refers to a real, reachable transport.
 *
 * Valid values:
 *   • HTTP/HTTPS URL  — e.g. "http://localhost:7071"  (Streamable HTTP MCP)
 *   • File-system path to oxygen.bat / oxygen.sh
 *     — e.g. "C:\\Program Files\\Oxygen XML Author 28\\oxygen.bat"
 *     — e.g. "/opt/oxygen/oxygen.sh"
 *
 * Invalid (returns false):
 *   • Empty string — not yet configured.
 *   • "stdio://oxygen-xml-28" — the default Settings placeholder; the user
 *     must replace it with an actual path or HTTP URL before the provider
 *     becomes available.  A bare `stdio://` URI is NOT a valid path.
 */
function endpointConfigured(ep: string): boolean {
  if (!ep) return false;
  if (ep === "stdio://oxygen-xml-28") return false;
  return ep.startsWith("http://") || ep.startsWith("https://") || ep.includes("\\") || ep.includes("/");
}

function isHttpEndpoint(ep: string): boolean {
  return ep.startsWith("http://") || ep.startsWith("https://");
}

/**
 * Creates an McpPort backed by the Rust `mcp_call` (HTTP) or `mcp_stdio_call`
 * (Oxygen local server) commands.
 *
 * `getEndpoint` is called lazily so Settings changes are picked up without
 * re-creating the port (same pattern as makeLlmPortFromSettings).
 */
export function makeTauriMcp(getEndpoint: () => string): McpPort {
  async function invoke<T>(method: string, params: Record<string, unknown>): Promise<T> {
    const ep = getEndpoint();
    if (isHttpEndpoint(ep)) {
      return bridge().core.invoke<T>("mcp_call", { endpoint: ep, method, params });
    }
    // Treat as a file-system path to oxygen.bat / oxygen.sh (stdio transport).
    return bridge().core.invoke<T>("mcp_stdio_call", { exePath: ep, method, params });
  }

  return {
    isAvailable(): boolean {
      return tauriAvailable() && endpointConfigured(getEndpoint());
    },

    async listTools(): Promise<McpTool[]> {
      const result = await invoke<{ tools?: McpTool[] }>("tools/list", {});
      return result?.tools ?? [];
    },

    async callTool(name: string, args: Record<string, unknown>): Promise<McpCallResult> {
      return invoke<McpCallResult>("tools/call", { name, arguments: args });
    },
  };
}

/**
 * Write a temporary COPY of the document to disk and return its absolute path
 * (E5a / ADR-0019). The copy gives a read-only MCP tool a file location for the
 * "current document"; the original file and its save target are never exposed.
 */
export async function writeTempDoc(content: string): Promise<string> {
  return bridge().core.invoke<string>("write_temp_doc", { content });
}
