export const requirementCategories = [
  "conditions", "personnel", "support", "supplies", "spares", "safety",
] as const;
export const procedureCategories = [...requirementCategories, "common", "closing"] as const;
export const reviewDestinations = [...procedureCategories, "body", "discard"] as const;
export type ReviewDestination = (typeof reviewDestinations)[number];

export type ReviewPassage = {
  id: string;
  node_id: string;
  row: number | null;
  start: number;
  end: number;
  source_text: string;
  text: string;
  page: number | null;
  kind: string;
  role?: "content" | "heading" | "table-header" | "marker" | "layout" | "caption";
  phase?: "unknown" | "preliminary" | "main" | "common" | "closing";
  suggested: ReviewDestination | "review";
  rule: "keywords" | "heading" | "multiple" | "unmatched" | "main" | "closing" | "common" | "action" | "structure" | "admonition";
  decision: ReviewDestination | null;
};

export function isReviewable(passage: ReviewPassage): boolean {
  return passage.role === undefined || passage.role === "content";
}

export type ReaderPosition = {
  page: number;
  scroll_top: number;
  selected_id: string | null;
};

export type ProcedureReview = {
  fingerprint: string;
  rules_revision?: number;
  status: "pending" | "reviewed" | "skipped" | "stale";
  passages: ReviewPassage[];
  position: ReaderPosition;
  saved_at: string | null;
};

export type PreliminaryState = {
  revision: number;
  active_dm_id: string | null;
  source_format: string;
  source_changed: boolean;
  reviews: Record<string, ProcedureReview>;
};

export type ReviewAction = {
  dm_id: string;
  op: "decide" | "split" | "complete" | "restart" | "cursor" | "skip";
  passage_id?: string;
  destination?: ReviewDestination | null;
  text?: string;
  split_at?: number;
  confirm_empty?: boolean;
  page?: number;
  scroll_top?: number;
  selected_id?: string | null;
};

export type SourcePage = { page: number; width: number; height: number };
export type PageAnchors = {
  width: number;
  height: number;
  anchors: Record<string, Array<[number, number, number, number]>>;
};
