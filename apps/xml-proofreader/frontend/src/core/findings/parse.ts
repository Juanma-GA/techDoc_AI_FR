// Robust parser for the model's JSON findings response. Reused by the AI
// Proofreader and (Chunk 23) the AI Chat "detect issues" flow.
import type { IssueSeverity } from "../issues/types";
import type { Finding } from "./types";

export interface ParsedFindings {
  findings: Finding[];
  /** Set when the response could not be parsed into a findings array. */
  error?: string;
}

function normalizeSeverity(raw: unknown): IssueSeverity {
  if (raw === "error" || raw === "warning" || raw === "info") return raw;
  return "warning";
}

function coerceString(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

/**
 * Parses the JSON text returned by the model into Findings.
 *
 * On failure returns `{ findings: [], error }` (never throws), so callers decide
 * how to surface the problem (the proofreader emits an info-level Issue; the
 * chat shows an error bubble).
 */
export function parseFindings(text: string): ParsedFindings {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { findings: [], error: `unparseable response: ${text.slice(0, 120)}` };
  }

  const arr = (parsed as { findings?: unknown } | null)?.findings;
  if (!Array.isArray(arr)) {
    return { findings: [], error: "response did not contain a findings array" };
  }

  const findings: Finding[] = arr.map((raw) => {
    const f = (raw ?? {}) as Record<string, unknown>;
    return {
      rule: coerceString(f.rule),
      severity: normalizeSeverity(f.severity),
      message: coerceString(f.message),
      quote: typeof f.quote === "string" ? f.quote : "",
      replacement: typeof f.replacement === "string" ? f.replacement : undefined,
    };
  });

  return { findings };
}
