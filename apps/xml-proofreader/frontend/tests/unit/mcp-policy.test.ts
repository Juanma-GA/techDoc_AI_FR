// Tests for Chunk 27 (D9): read-only MCP allowlist (core/issues/mcp-policy.ts).
import { describe, it, expect } from "vitest";
import { isToolAllowed, filterAllowedTools, toolBlockedReason } from "../../src/core/issues/mcp-policy";

describe("isToolAllowed (default-deny read-only allowlist)", () => {
  it("allows read-only / consultative tools", () => {
    for (const name of [
      "validate_document", "validateXml", "check_links", "lint_dita",
      "query_schema", "search_content", "get_outline", "list_topics",
      "read_metadata", "analyze_structure", "diagnostics", "describe_element",
    ]) {
      expect(isToolAllowed(name), name).toBe(true);
    }
  });

  it("blocks mutating tools", () => {
    for (const name of [
      "write_file", "edit_element", "modify_attribute", "update_topic",
      "delete_node", "remove_comment", "create_topic", "insert_element",
      "replace_text", "refactor_map", "format_document", "save_file",
      "rename_id", "apply_patch", "set_attribute", "move_node",
      "transform_dita", "generate_topic", "commit_changes", "fix_errors",
    ]) {
      expect(isToolAllowed(name), name).toBe(false);
    }
  });

  it("blocks a tool that is both read-only and mutating (mutating wins)", () => {
    expect(isToolAllowed("validate_and_save")).toBe(false);
  });

  it("blocks unknown / unrecognised names (default-deny)", () => {
    expect(isToolAllowed("frobnicate")).toBe(false);
    expect(isToolAllowed("")).toBe(false);
  });
});

describe("filterAllowedTools", () => {
  it("keeps only allowed tools, preserving order", () => {
    const tools = [
      { name: "validate_document" },
      { name: "save_file" },
      { name: "check_links" },
      { name: "edit_element" },
    ];
    expect(filterAllowedTools(tools).map((t) => t.name)).toEqual([
      "validate_document",
      "check_links",
    ]);
  });
});

describe("toolBlockedReason", () => {
  it("mentions the tool name and the read-only policy", () => {
    const r = toolBlockedReason("delete_node");
    expect(r).toContain("delete_node");
    expect(r).toMatch(/read-only/i);
  });
});
