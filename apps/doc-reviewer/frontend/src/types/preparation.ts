export type OcrProvider = "mistral" | "paddle" | "indra";

export type OcrProviderInfo = {
  id: OcrProvider;
  label: string;
  available: boolean;
  external: boolean;
  reason: string | null;
};

export type OcrBox = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  text: string;
  confidence: number | null;
};

export type OcrPageResult = {
  page: number;
  provider: OcrProvider;
  text: string;
  boxes: OcrBox[];
  elapsed_ms: number;
};

export type PreparationPage = {
  page: number;
  native_text_chars: number;
  native_text_usable: boolean;
  needs_ocr: boolean;
  width: number;
  height: number;
};

export type PreparationRuleResult = {
  rule_id: string;
  title: string;
  message: string;
  status: "PASS" | "FAIL" | "MANUAL" | "INCONCLUSIVE" | "UNSUPPORTED";
};

export type PreparationFailure = {
  rule_id: string;
  title: string;
  message: string;
  status: string;
};

export type PreparationPageDecision = {
  page: number;
  page_type: string | null;
  is_modified: boolean | null;
  decision_status: "selected" | "not_selected" | "needs_review" | "no_applicable_rule";
  rule_results: PreparationRuleResult[];
  failures: PreparationFailure[];
  review_reasons: PreparationFailure[];
  toc_page: number | null;
  toc_bbox: number[] | null;
  toc_entry?: string | null;
  manual_override?: boolean;
  page_type_source?: "auto" | "manual" | "unclassified";
  detected_page_type?: string | null;
  page_title?: string | null;
  document_page?: string | null;
  document_page_source?: "auto" | "manual";
  classification_evidence?: {
    footer_lines: string[];
    footer_page_key: string | null;
  };
  classification_status?:
    | "confirmed"
    | "partial"
    | "detected"
    | "conflict"
    | "unclassified"
    | "manual";
  classification_signals?: { section: string; family: string; detail: string }[];
  classification_candidates?: string[];
  classification_notes?: string[];
};

export type PreparationPageTitleOption = {
  title: string;
  page_type: string;
};

export type PreparationState = {
  document_id: string;
  source_filename: string | null;
  source_sha256: string | null;
  page_count: number;
  selected_provider: OcrProvider | null;
  pages: PreparationPage[];
  ocr_results_available: { provider: OcrProvider; page: number }[];
  validated_pages: number[];
  checklist_rule_count: number;
  checklist_imported_rule_count: number;
  preparation_rule_count: number;
  checklist_source_filename: string | null;
  page_decisions: PreparationPageDecision[];
  preparation_mapping: Record<string, unknown>;
  page_classification?: Record<
    string,
    { page_type: string | null; document_page: string | null; page_title?: string | null }
  >;
  page_type_options?: string[];
  page_title_options?: PreparationPageTitleOption[];
  missing_page_types?: string[][];
  absent_page_types?: string[][];
  skipped_rules?: PreparationSkippedRule[];
};

export type PreparationSkippedRule = {
  rule_id: string;
  title: string;
  page_types: string[];
};

export type PreparationPageText = {
  page: number;
  text: string;
};
