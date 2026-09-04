// MCP arg coercion + document-param detection (E5 / ADR-0023).
import { describe, it, expect } from "vitest";
import { coerceToolArgs, findDocumentPathParam, type JsonSchema } from "../../src/core/mcp/args";

describe("coerceToolArgs", () => {
  it("passes a plain object through unchanged", () => {
    expect(coerceToolArgs({ keywords: ["a", "b"] })).toEqual({ keywords: ["a", "b"] });
  });

  it("parses a JSON string into an object (the find_reusable_components bug)", () => {
    expect(coerceToolArgs('{"keywords":["pump","valve"]}')).toEqual({ keywords: ["pump", "valve"] });
  });

  it("treats null/undefined/empty-string as no args", () => {
    expect(coerceToolArgs(undefined)).toEqual({});
    expect(coerceToolArgs(null)).toEqual({});
    expect(coerceToolArgs("   ")).toEqual({});
  });

  it("throws a clear error on a non-JSON string", () => {
    expect(() => coerceToolArgs("not json")).toThrow(/not valid JSON/i);
  });

  it("throws when the value is JSON but not an object", () => {
    expect(() => coerceToolArgs("[1,2,3]")).toThrow(/must be a JSON object/i);
    expect(() => coerceToolArgs("42")).toThrow(/must be a JSON object/i);
  });

  it("validates declared property types and reports a mismatch", () => {
    const schema: JsonSchema = { properties: { strictness: { type: "string" } } };
    expect(() => coerceToolArgs({ strictness: 5 }, schema)).toThrow(/strictness.*string/i);
  });

  it("accepts matching types and tolerates integer↔number and unknown props", () => {
    const schema: JsonSchema = { properties: { n: { type: "number" }, s: { type: "string" } } };
    expect(coerceToolArgs({ n: 3, s: "x", extra: true }, schema)).toEqual({ n: 3, s: "x", extra: true });
  });
});

describe("findDocumentPathParam", () => {
  it("finds a string param whose name denotes a document path/URI", () => {
    expect(findDocumentPathParam({ properties: { documentURL: { type: "string" } } })).toBe("documentURL");
    expect(findDocumentPathParam({ properties: { systemId: { type: "string" } } })).toBe("systemId");
    expect(findDocumentPathParam({ properties: { filePath: {} } })).toBe("filePath"); // type-less ok
  });

  it("returns undefined when no property looks like a document path", () => {
    expect(findDocumentPathParam({ properties: { keywords: { type: "array" } } })).toBeUndefined();
    expect(findDocumentPathParam(undefined)).toBeUndefined();
    expect(findDocumentPathParam({})).toBeUndefined();
  });

  it("ignores a path-like name that is not a string type", () => {
    expect(findDocumentPathParam({ properties: { fileCount: { type: "number" } } })).toBeUndefined();
  });
});
