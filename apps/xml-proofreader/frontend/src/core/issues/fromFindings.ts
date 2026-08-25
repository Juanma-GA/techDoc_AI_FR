// Maps shared Findings (core/findings, defined by Chunk 20) onto the unified
// Issue model, anchored against a buffer. Used by the AI Chat "detect issues"
// flow (Chunk 23); the AI Proofreader has its own equivalent mapping in
// core/grader/parser.ts.
import type { Issue } from "./types";
import { anchorByQuote } from "./anchor";
import type { Finding } from "../findings/types";

let _counter = 0;

/** Convert Findings into anchored Issues. `suggestion` comes from `replacement`. */
export function findingsToIssues(findings: Finding[], buffer: string, idPrefix = "chat"): Issue[] {
  return findings.map((f) => ({
    id: `${idPrefix}-${Date.now()}-${++_counter}`,
    source: "proofreader",
    severity: f.severity,
    message: f.message,
    quote: f.quote || undefined,
    suggestion: f.replacement || undefined,
    anchor: anchorByQuote(buffer, f.quote),
  }));
}
