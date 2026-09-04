// ----------------------------------------------------------------
// State-history sidecar for comment threads (B7 / ADR-0004)
// Oxygen does not persist the history of state changes; we store
// it here, keyed by document URI → root comment id → entries.
// ----------------------------------------------------------------

export type CommentStatus = "open" | "resolved";

export interface CommentHistoryEntry {
  status: CommentStatus;
  /** Epoch millis when the state change was recorded. */
  timestamp: number;
  author: string;
}

/**
 * Per-document sidecar: state-change history for threaded comments.
 * Key = root comment Oxygen id (e.g. "q52_qnb_qjc").
 * Value = ordered list of state changes (oldest first, newest last).
 */
export type CommentHistorySidecar = Record<string, CommentHistoryEntry[]>;

// ----------------------------------------------------------------
// A company project the SME is assigned to. It fixes the expected structured
// language + issue/version and the repository it syncs to (sync is backlog, so
// the repository is only a reference for now).
export interface Project {
  id: string;
  name: string;
  language: "DITA" | "S1000D";
  /** Expected issue/version, e.g. "1.3" or "4.0". */
  issue: string;
  /** Repository reference (placeholder — real sync is a backlog item). */
  repositoryRef: string;
}

// Per-user workspace settings (persisted and associated to each user).
// Includes AI/MCP configuration (used by later blocks B8/B9) and preferences.
export interface Settings {
  projects: Project[];
  currentProjectId: string;
  ai: {
    /**
     * "anthropic" → Anthropic Messages API (claude-* models).
     * "openai-compat" → OpenAI Chat Completions-compatible endpoint
     *   (covers Mistral, OpenAI, self-hosted). Requires base_url.
     * ADR-0008: no vendor SDKs; transport is Rust/reqwest in the Tauri shell.
     */
    provider: "anthropic" | "openai-compat";
    /** Base URL for openai-compat endpoints, e.g. "https://api.mistral.ai/v1". */
    base_url?: string;
    model: string;
    apiKey: string;
    oxygenMcpEndpoint: string;
  };
  prefs: {
    uiLanguage: "en" | "fr";
    defaultHighlight: "yellow" | "green" | "pink" | "blue";
    showResolved: boolean;
  };
  /** SME semantic rules used by the AI Proofreader (block B9). */
  graderRules: string[];
}

/**
 * Whether a detected document language/version conflicts with the active
 * project's expectations. No document loaded ⇒ no mismatch.
 */
export function languageMismatch(
  detectedLanguage: string,
  detectedVersion: string,
  project: Project | undefined
): boolean {
  if (!detectedLanguage || !project) return false;
  if (detectedLanguage !== project.language) return true;
  if (project.issue && detectedVersion && detectedVersion !== project.issue) return true;
  return false;
}

export function defaultSettings(): Settings {
  return {
    projects: [
      { id: "br186", name: "Bogie Overhaul (BR186)", language: "DITA", issue: "1.3", repositoryRef: "ccms://atexis/br186" },
      { id: "flirt", name: "Traction S1000D (FLIRT)", language: "S1000D", issue: "4.0", repositoryRef: "\\\\fileserver\\flirt\\s1000d" },
    ],
    currentProjectId: "br186",
    ai: {
      provider: "anthropic",
      model: "claude-sonnet-4-6",
      apiKey: "",
      oxygenMcpEndpoint: "stdio://oxygen-xml-28",
    },
    prefs: { uiLanguage: "en", defaultHighlight: "yellow", showResolved: true },
    graderRules: [
      "Every torque value must cite the applicable technical note or standard.",
      "Do not mix measurement unit systems within a procedure (SI only).",
    ],
  };
}
