// OxygenIssueProvider: bridges Oxygen XML Author's MCP server → Issue[].
// Tauri-only (ADR-0002). isAvailable() returns false in browser and when the
// configured endpoint is empty or uses the unimplemented stdio:// scheme.

import type { McpPort } from "../../../ports/McpPort";
import type { IssueProvider, Issue } from "../types";
import { anchorByQuote } from "../anchor";
import { filterAllowedTools } from "../mcp-policy";

let _idSeq = 0;
function nextId(): string {
  return `oxygen-${++_idSeq}`;
}

/**
 * Parses Oxygen's validation tool output into Issue[].
 *
 * Oxygen may return:
 * a) A JSON array/object with structured findings (attempted first).
 * b) Text lines such as:
 *    [ERROR]   file.dita:10:5: element "foo" not allowed here
 *    [WARNING] file.dita:20:1: attribute "id" required
 * c) Arbitrary text if the tool format is unknown (each non-empty line → warning).
 */
function parseValidationOutput(text: string, buffer: string): Issue[] {
  const issues: Issue[] = [];

  // --- Try structured JSON ---
  try {
    const parsed = JSON.parse(text);
    const findings: unknown[] = Array.isArray(parsed)
      ? parsed
      : (parsed.findings ?? parsed.issues ?? parsed.results ?? []);
    for (const f of findings as Record<string, unknown>[]) {
      const issue: Issue = {
        id: nextId(),
        source: "oxygen",
        severity:
          String(f.severity ?? "warning").toLowerCase() === "error" ? "error"
          : String(f.severity ?? "warning").toLowerCase() === "info" ? "info"
          : "warning",
        message: String(f.message ?? f.msg ?? f.description ?? JSON.stringify(f)),
      };
      const quote = String(f.quote ?? f.text ?? "");
      if (quote) {
        issue.quote = quote;
        issue.anchor = anchorByQuote(buffer, quote) ?? undefined;
      }
      issues.push(issue);
    }
    return issues;
  } catch {
    // Fall through to text parsing
  }

  // --- Try bracketed severity pattern: [ERROR] ...: message ---
  const lineRe = /\[(ERROR|WARNING|INFO)\][^\n]*:\s*(.+)/gi;
  let m: RegExpExecArray | null;
  while ((m = lineRe.exec(text)) !== null) {
    const sev = m[1].toUpperCase();
    issues.push({
      id: nextId(),
      source: "oxygen",
      severity: sev === "ERROR" ? "error" : sev === "INFO" ? "info" : "warning",
      message: m[2].trim(),
    });
  }
  if (issues.length > 0) return issues;

  // --- Fallback: each non-empty line is a warning ---
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (t) issues.push({ id: nextId(), source: "oxygen", severity: "warning", message: t });
  }
  return issues;
}

export class OxygenIssueProvider implements IssueProvider {
  readonly id = "oxygen" as const;
  readonly label = "Oxygen MCP";

  constructor(private mcp: McpPort) {}

  isAvailable(): boolean {
    return this.mcp.isAvailable();
  }

  async run(buffer: string): Promise<Issue[]> {
    // 1. Discover which tools the MCP server exposes.
    let tools: { name: string }[];
    try {
      tools = await this.mcp.listTools();
    } catch (e) {
      return [{
        id: nextId(), source: "oxygen", severity: "error",
        message: `Oxygen MCP: cannot reach server — ${e}`,
      }];
    }

    // 2. Find a validation tool among the read-only-allowed tools (D9). The
    //    allowlist guarantees we never invoke a mutating tool by heuristic.
    const allowed = filterAllowedTools(tools);
    const validationTool = allowed.find((t) => /validat/i.test(t.name));
    if (!validationTool) {
      const names = allowed.map((t) => t.name).join(", ") || "(none)";
      return [{
        id: nextId(), source: "oxygen", severity: "info",
        message: `Oxygen MCP is connected but no validation tool was found. Available tools: ${names}`,
      }];
    }

    // 3. Call the validation tool with the document content.
    let result;
    try {
      result = await this.mcp.callTool(validationTool.name, { content: buffer });
    } catch (e) {
      return [{ id: nextId(), source: "oxygen", severity: "error", message: `Oxygen MCP: ${e}` }];
    }

    if (result.isError) {
      const msg = result.content.map((c) => c.text ?? "").join("\n").trim();
      return [{
        id: nextId(), source: "oxygen", severity: "error",
        message: `Oxygen MCP reported an error: ${msg || "(no detail)"}`,
      }];
    }

    const text = result.content.map((c) => c.text ?? "").join("\n");
    if (!text.trim()) return [];
    return parseValidationOutput(text, buffer);
  }
}
