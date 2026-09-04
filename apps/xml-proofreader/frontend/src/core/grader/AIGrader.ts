// AIGrader — IssueProvider that uses LlmPort to apply SME semantic rules.

import type { Issue, IssueProvider } from "../issues/types";
import type { LlmPort } from "../../ports/LlmPort";
import { buildGraderRequest, CONTEXT_LIMIT_THRESHOLD } from "./prompt";
import { parseGraderResponse } from "./parser";

export class AIGrader implements IssueProvider {
  readonly id = "proofreader" as const;
  readonly label = "AI Proofreader";

  constructor(
    private readonly llm: LlmPort,
    private readonly rules: () => string[],
    private readonly model: () => string
  ) {}

  isAvailable(): boolean {
    return this.llm.isAvailable();
  }

  async run(buffer: string): Promise<Issue[]> {
    const rules = this.rules();
    if (rules.length === 0) {
      return [
        {
          id: `proofreader-norules-${Date.now()}`,
          source: "proofreader",
          severity: "info",
          message: "No proofreading rules configured. Add rules in the AI Proofreader tab.",
        },
      ];
    }

    if (buffer.length > CONTEXT_LIMIT_THRESHOLD) {
      return [
        {
          id: `proofreader-toolarge-${Date.now()}`,
          source: "proofreader",
          severity: "info",
          message: `Document exceeds the context limit threshold (${buffer.length} chars). Chunked proofreading is not yet supported.`,
        },
      ];
    }

    const req = buildGraderRequest(rules, buffer, this.model());
    const text = await this.llm.complete(req);
    return parseGraderResponse(text, buffer);
  }
}
