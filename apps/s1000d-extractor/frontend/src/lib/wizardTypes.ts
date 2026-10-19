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
