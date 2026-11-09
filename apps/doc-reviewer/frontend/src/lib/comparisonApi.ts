import { API_BASE_URL, api } from "./api";

export type ComparisonBbox = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  page_w: number;
  page_h: number;
  page_rotation: number;
};

export type ComparisonChange = {
  group_id: string;
  kind: "added" | "removed";
  page: number;
  text: string;
  bbox: ComparisonBbox | null;
};

export type ComparisonPageAlignment = {
  slot_id: string;
  reference_page: number | null;
  comparison_page: number | null;
  status: "aligned" | "changed" | "reference_only" | "comparison_only";
};

export type ComparisonPageSlot = {
  id: string;
  reference_page: number | null;
};

export type ComparisonDocumentInfo = {
  index: number;
  filename: string;
  page_count: number;
};

export type ComparisonPair = {
  document_index: number;
  filename: string;
  added_count: number;
  removed_count: number;
  changes: ComparisonChange[];
  page_alignment: ComparisonPageAlignment[];
};

export type ComparisonReport = {
  schema_version: 5;
  reference_index: number;
  documents: ComparisonDocumentInfo[];
  comparisons: ComparisonPair[];
  page_slots: ComparisonPageSlot[];
};

export type ComparisonAiSummary = {
  summary: string;
  key_changes: string[];
  impact: string;
};

export type ComparisonListItem = {
  id: string;
  title: string;
  created_at: string;
  file_count: number;
  ai_status: string;
};

export type ComparisonDetail = ComparisonListItem & {
  report: ComparisonReport;
  ai_summary: ComparisonAiSummary | null;
  ai_summary_truncated: boolean;
};

export type ComparisonSynthesis = {
  ai_status: string;
  ai_summary: ComparisonAiSummary | null;
  ai_summary_truncated: boolean;
};

export const comparisonApi = {
  list: () => api.get<ComparisonListItem[]>("/comparisons"),
  read: (id: string) => api.get<ComparisonDetail>(`/comparisons/${id}`),
  create: (files: File[], referenceIndex: number, pageSimilarityThreshold = 85) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("reference_index", String(referenceIndex));
    formData.append("page_similarity_threshold", String(pageSimilarityThreshold));
    return api.upload<ComparisonDetail>("/comparisons", formData);
  },
  synthesize: (id: string, language: "fr" | "en") =>
    api.post<ComparisonSynthesis>(`/comparisons/${id}/synthesis`, { language }),
  delete: (id: string) => api.delete<void>(`/comparisons/${id}`),
  exportUrl: (id: string, language: "fr" | "en") =>
    `${API_BASE_URL}/comparisons/${id}/export?language=${language}`,
  exportDocumentUrl: (id: string, index: number, language: "fr" | "en") =>
    `${API_BASE_URL}/comparisons/${id}/export/${index}?language=${language}`,
  pageImageUrl: (id: string, index: number, page: number) =>
    `${API_BASE_URL}/comparisons/${id}/documents/${index}/pages/${page}.png`,
};
