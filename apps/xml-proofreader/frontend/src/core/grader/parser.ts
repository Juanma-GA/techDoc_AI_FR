// Parses the AI Proofreader JSON response into Issue[].
// Findings are parsed by core/findings and anchored by the shared locateQuote.

import type { Issue } from "../issues/types";
import { anchorByQuote } from "../issues/anchor";
import { parseFindings } from "../findings/parse";

let _idCounter = 0;
function nextId(): string {
  return `proofreader-${Date.now()}-${++_idCounter}`;
}

/**
 * Parses the text response from the LLM into Issue[].
 * Returns a single info-level issue if the response cannot be parsed.
 *
 * `suggestion` comes from the finding's `replacement` (the corrected text) — not
 * from the rule. Each issue is anchored by its quote via the normalized matcher.
 */
export function parseGraderResponse(text: string, buffer: string): Issue[] {
  const { findings, error } = parseFindings(text);
  if (error) {
    return [
      {
        id: nextId(),
        source: "proofreader",
        severity: "info",
        message: `AI Proofreader: ${error}`,
      },
    ];
  }

  return findings.map((f) => ({
    id: nextId(),
    source: "proofreader",
    severity: f.severity,
    message: f.message,
    quote: f.quote || undefined,
    suggestion: f.replacement || undefined,
    anchor: anchorByQuote(buffer, f.quote),
  }));
}
