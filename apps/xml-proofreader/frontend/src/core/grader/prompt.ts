// Builds the structured prompt for the AI Proofreader from rules + XML buffer.

import type { LlmRequest } from "../../ports/LlmPort";

const SYSTEM = `You are an expert technical documentation reviewer for structured DITA and S1000D content.
You receive a list of semantic rules and an XML document. Your task is to identify findings where the document violates the rules.

Respond ONLY with a valid JSON object matching this schema:
{
  "findings": [
    {
      "rule": "<the rule that was violated>",
      "severity": "error" | "warning" | "info",
      "message": "<concise explanation of the violation>",
      "quote": "<verbatim excerpt of human-visible text only — no XML tags, attributes or markup — max 200 chars>",
      "replacement": "<the corrected text that should replace the quote, or null if not applicable>"
    }
  ]
}

For "quote", copy the visible text exactly as a reader sees it: do not include any XML tags or attributes, and keep it within a single element (a contiguous run of text). This lets the app locate and, when a "replacement" is given, apply the fix.
If there are no violations, respond with { "findings": [] }.
Do not include any text outside the JSON object.`;

export function buildGraderRequest(
  rules: string[],
  buffer: string,
  model: string,
  maxTokens = 2048
): LlmRequest {
  const rulesBlock = rules.map((r, i) => `${i + 1}. ${r}`).join("\n");
  const content = `RULES:\n${rulesBlock}\n\nDOCUMENT:\n${buffer}`;
  return { system: SYSTEM, content, model, maxTokens, jsonMode: true };
}

/** Informational issue emitted when the document is too large for the model context. */
export const CONTEXT_LIMIT_THRESHOLD = 200_000; // characters (rough proxy for tokens)
