export type Severity = "info" | "warning" | "error";

export type RuleKind =
  | "standard"
  | "custom"
  | "units"
  | "layout"
  | "vision"
  | "compiled_standard"
  | "compiled_checklist";

/** Provenance affichee/filtrable dans la liste des anomalies. */
export type SourceKind = "norme" | "checklist" | "regle" | "transverse";

export type RuleKindStored =
  | "regex_replace"
  | "regex_flag"
  | "term_replace"
  | "case_capitalize"
  | "accent_fix"
  | "field_required"
  | "section_required"
  | "field_consistency"
  | "step_pattern"
  | "enum_value"
  // Style : longueur de phrase (seuil de mots), non exprimable en regex.
  | "sentence_length"
  // Import checklist : consigne NL jugee par le LLM / verification humaine.
  | "llm_nl"
  | "manual";

export type SuggestionStatus = "open" | "accepted" | "edited" | "rejected" | "applied";

export type EvidenceLocation =
  | { type: "bbox"; bbox: [number, number, number, number] }
  | { type: "target_id"; target_id: string };

export type RuleResult = {
  rule_id: string;
  status: "PASS" | "FAIL" | "MANUAL" | "UNSUPPORTED" | "INCONCLUSIVE";
  evidence: {
    page: string;
    location: EvidenceLocation;
    observed_value: string | null;
    expected_value: string | null;
  } | null;
};

export type Bbox = {
  x0: number | null;
  y0: number | null;
  x1: number | null;
  y1: number | null;
  page_w?: number;
  page_h?: number;
  page_rotation?: number;
};

export type Suggestion = {
  id: string;
  document_id: string;
  run_id: string | null;
  rule_kind: RuleKind;
  rule_code: string;
  source_kind: SourceKind;
  severity: Severity;
  message: string;
  original_text: string;
  proposed_text: string;
  page: number;
  bbox: Bbox;
  span_index: number;
  /** Pipeline docx natif : bloc cible ("dp<N>"), null pour les suggestions PDF. */
  target_id: string | null;
  status: SuggestionStatus;
  /** Motif libre de rejet (corpus-agent-style), renseigne au rejet. */
  feedback: string;
  applied_at: string | null;
  applied_version: number | null;
  created_at: string;
};

export type QualityState = "analyzable" | "degraded" | "unusable";

// Synthese IA des rejets : agregat par regle + paragraphe de synthese Mistral
// (garde par l'interrupteur LLM cote backend).
export type RejectionRuleCount = { rule_code: string; count: number };
export type RejectionItem = {
  id: string;
  file: string;
  rule_code: string;
  severity: string;
  message: string;
  feedback: string;
};
export type RejectionsSummary = {
  total: number;
  by_rule: RejectionRuleCount[];
  items: RejectionItem[];
  synthese: string;
  llm_used: boolean;
};

export type Document = {
  id: string;
  original_filename: string;
  sha256: string;
  page_count: number;
  target_unit_system: "metric" | "imperial" | "auto";
  standard_version_id: string | null;
  status: "uploaded" | "analyzing" | "analyzed" | "edited" | "analysis_failed";
  current_version: number;
  /** Pipeline de revue : "pdf" (defaut) ou "docx" (Word natif). */
  source_format: "pdf" | "docx";
  working_format: "pdf" | "docx";
  // Portail qualite : revuabilite homogene tous formats.
  convert_engine: string;
  text_coverage: number;
  quality: QualityState;
  /** Mapping manuel par document, reference par les consignes de checklist. */
  meta_revision_date: string | null;
  meta_cmm_number: string | null;
  meta_first_issue_date: string | null;
  meta_revision_number: string | null;
  document_language: "fr" | "en" | null;
  created_at: string;
};

export const REQUIRED_DOCUMENT_CONTEXT_FIELDS = [
  "meta_revision_date",
  "meta_cmm_number",
  "meta_first_issue_date",
  "meta_revision_number",
  "document_language",
] as const;

export type DocumentContextField = (typeof REQUIRED_DOCUMENT_CONTEXT_FIELDS)[number];

export function missingDocumentContext(
  document: Pick<
    Document,
    | "meta_revision_date"
    | "meta_cmm_number"
    | "meta_first_issue_date"
    | "meta_revision_number"
    | "document_language"
  > | null | undefined,
): DocumentContextField[] {
  if (!document) return [...REQUIRED_DOCUMENT_CONTEXT_FIELDS];
  return REQUIRED_DOCUMENT_CONTEXT_FIELDS.filter(
    (field) => !String(document[field] ?? "").trim(),
  );
}

export type Rule = {
  id: string;
  name: string;
  kind: RuleKindStored;
  pattern: string;
  replacement: string;
  severity: Severity;
  message: string;
  enabled: boolean;
  standard_version_id: string | null;
  created_at: string;
  updated_at: string;
};

export type StandardVersion = {
  id: string;
  standard_id: string;
  label: string;
  builtin: boolean;
  created_at: string;
  updated_at: string;
};

export type Standard = {
  id: string;
  code: string;
  label: string;
  description: string | null;
  builtin: boolean;
  versions: StandardVersion[];
  created_at: string;
  updated_at: string;
};

export type CatalogRule = {
  code: string;
  title: string;
  description: string;
  kind: RuleKindStored;
  severity: Severity;
  pattern: string;
  replacement: string;
  message: string;
  example_invalid: string;
  example_valid: string;
  metadata: Record<string, string>;
};

export type StandardVersionDetail = StandardVersion & {
  catalog: CatalogRule[];
  custom_rules: Rule[];
};

export type SuggestionApplyResult = {
  suggestion_id: string;
  document_id: string;
  new_version: number;
  snapshot_path: string;
  font_used: string;
  fallback_used: boolean;
  length_delta: number;
};

export type SuggestionGroupApplyResult = {
  suggestion_id: string;
  document_id: string;
  new_version: number;
  applied_count: number;
  skipped_count: number;
  applied_ids: string[];
  pages: number[];
};

export type StandardVersionId = string | null;

// Admin reset results (Data view). Mirror the backend `/admin/*` shapes:
// `POST /admin/wipe-suggestions` -> {deleted}; `POST /admin/reset` ->
// {documents_deleted, storage_folders_cleaned, orphan_folders_cleaned}.
export type WipeSuggestionsResult = {
  deleted: number;
};

export type ResetAllResult = {
  documents_deleted: number;
  rules_deleted: number;
  checklist_rules_deleted: number;
  storage_folders_cleaned: number;
  orphan_folders_cleaned: number;
};
