// Port for Model Context Protocol (MCP) client access. Tauri-only (ADR-0002);
// the browser adapter always returns isAvailable() = false.

export interface McpTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export interface McpContentBlock {
  type: "text" | "image" | string;
  text?: string;
}

export interface McpCallResult {
  content: McpContentBlock[];
  isError?: boolean;
}

export interface McpPort {
  /** False in browser and when no MCP endpoint is configured. */
  isAvailable(): boolean;
  listTools(): Promise<McpTool[]>;
  callTool(name: string, args: Record<string, unknown>): Promise<McpCallResult>;
}
