// Shared AI "finding" model. Both the AI Proofreader (grader) and the AI Chat
// "detect issues" flow parse the model's JSON into Findings, then map them to
// the unified Issue model. Keeping the shape here avoids divergence (ADR-0015).
import type { IssueSeverity } from "../issues/types";

export interface Finding {
  /** The rule (or check) that was violated. */
  rule: string;
  severity: IssueSeverity;
  /** Human-readable explanation of the violation. */
  message: string;
  /** Verbatim excerpt of visible text the finding refers to. */
  quote: string;
  /** Suggested replacement text for `quote`, when the model proposes one. */
  replacement?: string;
}
