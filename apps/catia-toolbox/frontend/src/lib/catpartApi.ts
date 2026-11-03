import { request, requestBlob } from "./apiClient";

export type CatpartSinMatchDto = {
  sin: string;
  old_pns: string[];
  new_pns: string[];
  old_files: string[];
  new_files: string[];
};

export type CatpartSameGeDto = {
  sin: string;
  pn: string;
  old_files: string[];
  new_files: string[];
};

export type CatpartSoloDto = {
  sin: string;
  pn: string;
  file: string;
};

export type CatpartCompareDto = {
  status: "complete" | "partial" | "empty";
  old_count: number;
  new_count: number;
  matches: CatpartSinMatchDto[];
  same_ge: CatpartSameGeDto[];
  solo_a: CatpartSoloDto[];
  solo_b: CatpartSoloDto[];
  issues: { file: string | null; code: string; message: string }[];
};

export const catpartDiffApi = {
  compare: (oldPath: string, newPath: string) =>
    request<CatpartCompareDto>("/diff/catparts", {
      method: "POST",
      body: JSON.stringify({
        old_path: oldPath,
        new_path: newPath,
      }),
    }),
  exportExcel: (oldPath: string, newPath: string) =>
    requestBlob("/diff/catparts/export.xlsx", {
      method: "POST",
      headers: {
        Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
      body: JSON.stringify({
        old_path: oldPath,
        new_path: newPath,
      }),
    }),
};
