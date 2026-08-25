// Unified issue model. SME comments are a separate concept (Oxygen PIs); an
// Issue is a machine-generated finding (schema/support validation, and later
// Oxygen MCP, Acrolinx, HyperSTE, AI Proofreader — blocks B8/B9). Providers feed
// the same Issues panel.
import type { AnnotationRange } from "../model/types";

export type IssueSource = "schema" | "support" | "oxygen" | "acrolinx" | "hyperste" | "proofreader";
export type IssueSeverity = "error" | "warning" | "info";

export interface Issue {
  id: string;
  source: IssueSource;
  severity: IssueSeverity;
  message: string;
  /** Optional anchor into the document (so it can be highlighted). */
  anchor?: AnnotationRange;
  /** Quoted text the issue refers to, for display + re-anchoring. */
  quote?: string;
  /** Optional suggested replacement/fix. */
  suggestion?: string;
}

/** Anything that can produce issues for the open document. */
export interface IssueProvider {
  readonly id: IssueSource;
  readonly label: string;
  /** Whether this provider can run in the current runtime (e.g. Tauri-only). */
  isAvailable(): boolean;
  run(buffer: string): Promise<Issue[]>;
}
