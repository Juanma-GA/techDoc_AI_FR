export type DmrlMatchRank = "exact" | "prefix" | "contains" | "";

export type DmrlTypeIssue =
  | "missing_info_code"
  | "unmapped_info_code"
  | "unsupported_schema";

export type DmrlRow = {
  index: number;
  arbo: string;
  dmc: string;
  title: string;
  dm_type: string;
  dmrl_type?: string;
  info_code?: string;
  info_code_schema?: string;
  info_code_dm_type?: string;
  type_conflict?: boolean;
  type_issue?: DmrlTypeIssue | "";
  icn: string;
  is_pm_title: boolean;
  matched: boolean;
  match_rank: DmrlMatchRank;
  page: number | null;
  matched_text: string;
};

export type Candidate = { element: string; score?: number; rationale?: string };

export type NodeRef = { kind: string; target?: string; target_kind?: string; text?: string };

export type TreeNode = {
  id: string;
  kind: string;
  text: string;
  context: string;
  confidence: number | null;
  candidates: Candidate[];
  children: TreeNode[];
  level?: number | null;
  page?: number | null;
  zone?: string;
  table_header?: string[] | null;
  icn?: string | null;
  refs?: NodeRef[] | null;
};

export type WizardStep = "dmrl" | "split" | "type" | "structure" | "preliminary" | "generate";

export type PreviewSnippet = {
  text: string;
  page: number | null;
  kind: string;
  zone?: string;
};

export type DmPreview = { head: PreviewSnippet[]; tail: PreviewSnippet[]; total: number };

export type DmValidationStatus = "valid" | "invalid" | "needs_issue" | "unverifiable";

export type DmValidationViolation = {
  severity: "error" | "warning" | "info";
  rule: string;
  message: string;
  path: string;
  line?: number | null;
  column?: number | null;
  brex_rule_id?: string;
  brex_severity_level?: string;
};

export type WizardDm = {
  dm_id: string;
  dmc?: string;
  title: string;
  dm_type: string;
  node_count: number;
  tree: TreeNode;
  violation_count: number;
  has_xml?: boolean;
  preview?: DmPreview;
  missing_fields?: string[];
  xsd_valid?: boolean;
  xsd_violations?: DmValidationViolation[];
  brex_violations?: DmValidationViolation[];
  cir_unresolved?: string[];
  is_orphan?: boolean;
};

export type DmValidationResult = {
  filename: string;
  dmc: string;
  issue: string | null;
  schema: string | null;
  status: DmValidationStatus;
  error_count: number;
  violations: DmValidationViolation[];
  message?: string;
};

export type WizardResources = {
  dmrl_count: number;
  has_cir: boolean;
  has_brex_rules: boolean;
  has_dm_header: boolean;
  errors?: string[];
};

export type WizardState = {
  step: WizardStep;
  split_level: string;
  dmrl_dm_count?: number;
  steps?: WizardStep[];
  dms: WizardDm[];
  can_undo?: boolean;
  has_brex_profile?: boolean;
  illustration_errors?: number;
  resources?: WizardResources;
  dmrl?: DmrlRow[];
  preliminary?: import("./preliminaryTypes").PreliminaryState;
};

export type Override = { dm_id: string; node_id: string; element: string };
