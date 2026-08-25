// Curated action chips for the AI Chat panel.
// Conversational actions inject a natural-language prompt into the normal
// sendChat flow. Detection actions (`detect: true`) run the structured
// findings pipeline (jsonMode + core/findings) and render issue cards (D2).
export interface CuratedAction {
  label: string;
  prompt: string;
  /** When true, run the structured "detect issues" flow instead of free chat. */
  detect?: boolean;
}

export const CURATED_ACTIONS: CuratedAction[] = [
  {
    label: "Run Oxygen check",
    prompt:
      "Please run an Oxygen XML validation check on the current document using the available MCP tools and report any errors or warnings.",
  },
  {
    label: "Check grammar",
    detect: true,
    prompt:
      "Review the grammar, spelling, style and clarity of the document. Report each problem as a finding.",
  },
  {
    label: "Review structure",
    detect: true,
    prompt:
      "Review the structure of this document (organization, topic types, element usage). Report each problem as a finding.",
  },
];
