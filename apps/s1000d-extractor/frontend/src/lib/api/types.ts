import type { Schemas } from "./contracts";
export type HealthDto = Schemas["HealthResponse"];
export type AdminStatsDto = Required<Schemas["AdminStatsOut"]>;
export type AdminResetDto = Schemas["AdminResetOut"];
export type SettingsDto = Required<Schemas["SettingsOut"]>;
export type S1000dIssue = "4.1" | "4.2";
export type ContextHint = "mixed" | "descriptive" | "procedural";
export type BrexProfile = Pick<Schemas["BrexProfileOut"], "id" | "name" | "s1000d_issue">;
export type BrexObjectValue = Schemas["BrexObjectValueOut"];
export type BrexRule = Omit<Schemas["BrexRuleOut"], "support_status"> & {
  support_status: "automatic" | "contextual" | "unsupported";
};
export type UnsupportedBrexRule = Schemas["UnsupportedBrexRuleOut"];
export type BrexProfileDetail = BrexProfile & {
  dmc: string;
  dm_code: Record<string, string>;
  rules: BrexRule[];
  unsupported_rules: UnsupportedBrexRule[];
};
export type DocumentOut = Pick<Schemas["DocumentOut"], "id" | "filename" | "source_format" | "status"> &
  Partial<Omit<Schemas["DocumentOut"], "id" | "filename" | "source_format" | "status">>;
export type PdfCutCandidate = Schemas["PdfCutCandidateOut"];
export type PdfCutDetection = Schemas["PdfCutDetectionOut"];
export type ResourceKind = Schemas["ResourceUploadOut"]["kind"];
export type ResourceUploadDto = Schemas["ResourceUploadOut"];
export type MigrationInputKind = "document" | ResourceKind;
export type MigrationInputMapping = {
  issue: S1000dIssue | "5.0";
  context_hint: ContextHint;
  brex_id: string | null;
  files: Partial<Record<MigrationInputKind, { filename: string }>>;
};
