import { request } from "./apiClient";

export type CatpartGeometryQuality = "partial" | "complete";

export type CatpartExactMatchDto = {
  sha256: string;
  old_files: string[];
  new_files: string[];
  old_count: number;
  new_count: number;
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
  exact_matches: CatpartExactMatchDto[];
  candidates: CatpartCandidateDto[];
  unmatched_old: string[];
  unmatched_new: string[];
  issues: { file: string | null; code: string; message: string }[];
  reader: { available: boolean; required: boolean };
};

export const catpartDiffApi = {
  compare: (oldPath: string, newPath: string) =>
    request<CatpartCompareDto>("/diff/catparts", {
      method: "POST",
      body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    }),
};
