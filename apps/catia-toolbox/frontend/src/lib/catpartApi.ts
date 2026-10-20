import { request } from "./apiClient";

export type CatpartGeometryQuality = "partial" | "complete";

export type CatpartExactSummaryDto = {
  groups: number;
  old_files: number;
  new_files: number;
};

export type CatpartCandidateDto = {
  old_file: string;
  new_file: string;
  similarity: number;
  confidence: "low";
  old_geometry_quality: CatpartGeometryQuality;
  new_geometry_quality: CatpartGeometryQuality;
  binary_equal: boolean;
};

export type CatpartCompareDto = {
  status: "complete" | "partial" | "empty";
  old_count: number;
  new_count: number;
  exact: CatpartExactSummaryDto;
  candidates: CatpartCandidateDto[];
  unmatched_old: string[];
  unmatched_new: string[];
  issues: { file: string | null; code: string; message: string }[];
  geometry_status: "not_requested" | "not_needed" | "available" | "missing" | "limit_exceeded";
};

export const catpartDiffApi = {
  compare: (oldPath: string, newPath: string, includeGeometry = false) =>
    request<CatpartCompareDto>("/diff/catparts", {
      method: "POST",
      body: JSON.stringify({
        old_path: oldPath,
        new_path: newPath,
        include_geometry: includeGeometry,
      }),
    }),
};
