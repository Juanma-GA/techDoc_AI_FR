// MCP tool-argument helpers (E5 / ADR-0023). Pure, no IO — unit-testable.
//
// Two problems this solves, observed against the Oxygen MCP server:
//   • E5b — some models emit the tool `args` as a JSON *string* rather than an
//     object, so the server fails to deserialize them
//     ("Cannot deserialize value … [Source: (String)\"{\"keywords\":[…").
//     coerceToolArgs parses the string and does a light shape check against the
//     tool's inputSchema, so we never forward garbage.
//   • E5a — a tool that validates/reads "the current document"
//     (validate_current_document → "Could not determine location for file to
//     validate") needs a file location. We point it at a temporary COPY of the
//     in-memory buffer, never the original (ADR-0019). findDocumentPathParam
//     locates the inputSchema property that wants such a path.

/** Minimal view of a JSON Schema object (MCP `inputSchema`). */
export interface JsonSchema {
  type?: string;
  properties?: Record<string, JsonSchemaProp>;
  required?: string[];
  [k: string]: unknown;
}

export interface JsonSchemaProp {
  type?: string;
  [k: string]: unknown;
}

function truncate(s: string, n = 80): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

/** Maps a JSON value to its JSON Schema primitive type name. */
function jsonTypeOf(v: unknown): string {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
  return typeof v; // "string" | "boolean" | "object" | ...
}

/** A schema-declared "integer" accepts a JSON "integer"; "number" accepts both. */
function typeMatches(declared: string, actual: string): boolean {
  if (declared === actual) return true;
  if (declared === "number" && actual === "integer") return true;
  if (declared === "integer" && actual === "number") return true;
  return false;
}

/**
 * Light validation: for every provided arg that the schema declares a `type`
 * for, check the primitive type matches. Tolerant by design (E5 risk b):
 * unknown props, missing schema, and absent `required` props are NOT rejected
 * here — a doc-path param may still be injected by the caller after coercion.
 * Throws a clear Error on a genuine type mismatch.
 */
function validateAgainstSchema(args: Record<string, unknown>, schema?: JsonSchema): void {
  const props = schema?.properties;
  if (!props) return;
  for (const [key, value] of Object.entries(args)) {
    const declared = props[key]?.type;
    if (!declared) continue;
    const actual = jsonTypeOf(value);
    if (!typeMatches(declared, actual)) {
      throw new Error(`Argument "${key}" should be ${declared} but got ${actual}.`);
    }
  }
}

/**
 * Coerce raw tool arguments into a plain object, parsing a JSON string when the
 * model emitted one (E5b), then light-validating against `inputSchema`.
 * Throws a clear Error when the value can't be made into a JSON object or a
 * declared type is violated.
 */
export function coerceToolArgs(raw: unknown, inputSchema?: JsonSchema): Record<string, unknown> {
  let obj: unknown = raw ?? {};
  if (typeof obj === "string") {
    const s = obj.trim();
    if (s === "") {
      obj = {};
    } else {
      try {
        obj = JSON.parse(s);
      } catch {
        throw new Error(`Tool arguments are not valid JSON: ${truncate(s)}`);
      }
    }
  }
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    throw new Error("Tool arguments must be a JSON object.");
  }
  const args = obj as Record<string, unknown>;
  validateAgainstSchema(args, inputSchema);
  return args;
}

/** Property-name stems that denote "a path/URI to a document/file". */
const DOC_PATH_HINT = /(path|uri|url|file|systemid|location|document)/i;

/**
 * Find the inputSchema string-typed property that wants a document path/URI, so
 * the caller can fill it with a temp copy of the buffer (E5a). Returns the first
 * matching property name, or undefined when the tool declares no such param.
 * Type-less properties are accepted (Oxygen's schemas aren't always typed).
 */
export function findDocumentPathParam(inputSchema?: JsonSchema): string | undefined {
  const props = inputSchema?.properties;
  if (!props) return undefined;
  for (const [name, def] of Object.entries(props)) {
    const t = def?.type;
    if ((t === undefined || t === "string") && DOC_PATH_HINT.test(name)) return name;
  }
  return undefined;
}
