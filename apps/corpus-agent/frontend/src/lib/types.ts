/**
 * DTO du backend Corpus Agent (contrats depuis backend/app/schemas.py).
 * Séparés de api.ts pour garder ce dernier sous 200 lignes (règle de méthode).
 */

export type LlmStatus = "ok" | "untested" | "not_configured" | "disabled";

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  db: string;
  llm: LlmStatus | string;
};

export type ProjectOut = {
  id: string;
  name: string;
  description: string;
  vision_enabled: boolean;
  created_at: string;
};

export type ProjectCreate = {
  name: string;
  description?: string;
  vision_enabled?: boolean;
};

export type ProjectUpdate = {
  name?: string | null;
  description?: string | null;
  vision_enabled?: boolean | null;
};

export type FileVersionOut = {
  id: string;
  filename: string;
  sha256: string;
  size: number;
  uploaded_at: string;
};

export type FileOut = {
  id: string;
  current_name: string;
  mime_type: string;
  created_at: string;
  versions: FileVersionOut[];
};

export type UploadItemResult = {
  filename: string;
  ok: boolean;
  error?: string;
  skipped?: string;
  sha256?: string;
  size?: number;
};

export type UploadResult = { uploaded: UploadItemResult[] };

export type ReferenceColumnDef = {
  name: string;
  sheet: string;
  column: string;
  builtin: boolean;
};

export type ReferenceOut = {
  path: string | null;
  sheets: string[];
  columns: ReferenceColumnDef[];
  header_rows: Record<string, number>;
};

export type SheetColumnOut = { letter: string; header: string };

export type SheetPreviewOut = {
  header_row_detected: number;
  rows: string[][];
};

export type ReferenceMappingIn = {
  columns: { name: string; sheet?: string; column?: string }[];
  header_rows?: Record<string, number>;
};

export type AnalysisRunOut = {
  id: string;
  project_id: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "failed";
  summary: string;
};

export type AnomalyStatus = "open" | "acknowledged" | "fixed" | "rejected";
export type AnomalySeverity = "low" | "medium" | "high";
export type AnomalyConfidence = "elevee" | "moyenne" | "faible";

export type AnomalyOut = {
  id: string;
  project_id: string;
  file_version_id: string | null;
  type: string;
  // Categorie metier (Sujet de la regle checklist) — dimension de regroupement.
  category?: string;
  severity: AnomalySeverity | string;
  confidence: AnomalyConfidence | string;
  message: string;
  suggestion: string;
  message_key: string | null;
  message_params_json: string | null;
  suggestion_key: string | null;
  suggestion_params_json: string | null;
  location: string;
  status: AnomalyStatus;
  created_at: string;
  resolved_at: string | null;
};

export type ChatSessionOut = {
  id: string;
  project_id: string | null;
  scope_project_ids: string[];
  title: string;
  created_at: string;
};

export type ChatMessageOut = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | string;
  content: string;
  citations: string;
  created_at: string;
};

export type ChatAskIn = {
  session_id: string | null;
  project_ids: string[];
  question: string;
  lang: string;
};

export type KpiOut = {
  open_anomalies: number;
  anomalies_by_severity: Record<string, number>;
  anomalies_by_type: Record<string, number>;
  // Repartition par categorie metier (Sujet des regles checklist).
  anomalies_by_category: Record<string, number>;
  anomalies_by_status: Record<string, number>;
  anomalies_by_confidence: Record<string, number>;
  resolution_rate: number;
  anomalies_over_time: Array<{
    run_id: string;
    started_at: string;
    total: number;
    // Repartition des anomalies du run par categorie (Sujet de la checklist).
    categories: Record<string, number>;
  }>;
  top_files: Array<{ filename: string; count: number }>;
  top_rules: Array<{ rule: string; count: number }>;
  avg_age_days: number;
  avg_resolution_days: number;
  files_total: number;
  files_with_anomalies: number;
};

export type MistralSettingsOut = {
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  chat_model: string;
  embed_model: string;
  vision_model: string;
  llm_enabled: boolean;
  llm_tested: boolean;
};

export type MistralSettingsIn = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  embed_model?: string;
  vision_model?: string;
  llm_enabled?: boolean | null;
};

export type TestConnectionOut = { ok: boolean; message: string; models: string[] };

export type AdminStatsOut = {
  projects: number;
  files: number;
  file_versions: number;
  anomalies: number;
  analysis_runs: number;
  chat_sessions: number;
  chat_messages: number;
  document_chunks: number;
  storage_bytes: number;
  db_bytes: number;
};

export type AdminResetScope = "analyses" | "chat" | "all";
export type AdminResetOut = { scope: string; deleted: Record<string, number> };

export type CustomRule = {
  id?: string;
  label: string;
  consigne: string;
  severity?: string;
  // File de validation : false = importee en attente, true/absent = active.
  validated?: boolean;
  // Interrupteur d'activation en direct : false = desactivee (ne participe pas
  // a l'analyse mais reste editable/reactivable), true/absent = active.
  enabled?: boolean;
};

export type ChecklistImportMode = "replace" | "add" | "update" | "overwrite";

// Regle proposee par l'IA a partir d'un document de reference (from-spec).
export type SpecRule = { label: string; consigne: string; severity: string };
export type SpecExtractOut = { regles: SpecRule[]; count: number };

export type SheetInfo = { name: string; header_row: number; rows: string[][] };
export type SheetInspectOut = { sheets: SheetInfo[] };

export type ChecklistImportResult = {
  mode: string;
  imported: number;
  created: number;
  updated: number;
  replaced_count: number;
  skipped: string[];
  pending: number;
};

export type RulesLegacyOut = {
  rules: {
    regles_personnalisees?: CustomRule[];
    custom_rules?: CustomRule[];
    instructions_libres?: string;
    [k: string]: unknown;
  };
  overridden: boolean;
  editable?: boolean;
};

export type I18nLangOut = {
  lang: string;
  fallback: boolean;
  translations: Record<string, string>;
};

export type I18nListOut = { builtin: string[]; override: string[]; all: string[] };
