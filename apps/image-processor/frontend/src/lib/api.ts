/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

// Surchargeable au build (VITE_API_BASE_URL) pour un deploiement en sous-chemin
// IIS (ex. /app/<poc>/api/v1). Defaut relatif '/api/v1' en local.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type ApiError = {
  code: string;
  message: string;
  detail: unknown;
  request_id: string;
};

async function apiResponse(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" };
  }
  return response;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await apiResponse(path, init)).json()) as T;
}

export async function apiDelete(path: string): Promise<void> {
  await apiResponse(path, { method: "DELETE" });
}

async function formResponse(path: string, formData: FormData): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiError | null;
    const message =
      (typeof payload?.message === "string" && payload.message) ||
      (typeof payload?.detail === "string" && payload.detail) ||
      response.statusText ||
      "Request failed.";
    throw new Error(message);
  }
  return response;
}

export async function apiForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await formResponse(path, formData);
  const payload: unknown = await response.json().catch(() => null);
  if (payload === null) throw new Error("The server returned an unreadable response.");
  return payload as T;
}

async function exportImage(formData: FormData): Promise<{ blob: Blob; filename: string }> {
  const response = await formResponse("/image-processor/export", formData);
  const encodedName = response.headers.get("Content-Disposition")?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (!encodedName || response.headers.get("Content-Type")?.split(";")[0] !== "image/jpeg") {
    throw new Error("The server returned an invalid JPEG download.");
  }
  const filename = decodeURIComponent(encodedName);
  if (!filename.endsWith(".jpg")) throw new Error("The server returned an invalid JPEG filename.");
  return { blob: await response.blob(), filename };
}

// ----- Standard DTOs (STANDARD_POC.md - health/settings/admin) -------------

export type HealthDto = { status: string; version: string; db: string };

export type SettingsDto = { demo_enabled: boolean };
export type SettingsInput = {
  demo_enabled?: boolean;
};

export type AdminStatsDto = {
  documents: number;
  chunks: number;
  sessions: number;
  messages: number;
  total_size_bytes: number;
};

export type AdminResetDto = { scope: string; deleted: Record<string, number> };

export type ExcelColumnDto = {
  index: number;
  letter: string;
  header: string;
  label: string;
};

export type ExcelPieceDto = { row: number; name: string };
export type ExcelReplacementPairDto = { reference: string; replacement: string };

export type OcrLineDto = {
  text: string;
  confidence: number;
  box: number[][];
  matched_references: string[];
  original_box?: number[][] | null;
  box_offset_x?: number;
  box_offset_y?: number;
};

export type OcrReferenceSnapshotDto = {
  reference: string;
  found: boolean;
  line_indices: number[];
  replacement?: string;
  replacement_count?: number;
};

export type OcrReferenceUndoDto = {
  previous_image_value: string;
  previous_reference_index: number | null;
  previous_reference: OcrReferenceSnapshotDto | null;
  previous_matched_references: string[];
  previous_pair_source: "manual" | "excel" | "created";
  previous_pair_id: number;
  previous_pair_replacement: string;
  previous_pair_enabled: boolean;
};

export type OcrReferenceDto = OcrReferenceSnapshotDto & {
  undo?: OcrReferenceUndoDto | null;
};

export type OcrResultDto = {
  width: number;
  height: number;
  source_width: number;
  source_height: number;
  full_text: string;
  lines: OcrLineDto[];
  references: OcrReferenceDto[];
  edited_image: string;
  filename: string;
  replacement_font_size?: number | null;
};

export type LineReplacementDto = {
  edited_image: string;
  replacement_count: number;
  replacement_font_size: number | null;
};

export type ReappliedReplacementsDto = {
  edited_image: string;
  replacement_counts: number[];
  replacement_font_size: number | null;
};

export const healthApi = { read: () => api<HealthDto>("/health") };

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  resetAll: () => api<AdminResetDto>("/admin/reset/all", { method: "POST" }),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: SettingsInput) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
};

export const imageReplaceApi = {
  exportImage,
  excelSheets: (formData: FormData) =>
    apiForm<{ sheets: string[] }>("/image-processor/excel/sheets", formData),
  excelColumns: (formData: FormData) =>
    apiForm<{ columns: ExcelColumnDto[] }>("/image-processor/excel/columns", formData),
  excelPieces: (formData: FormData) =>
    apiForm<{ pieces: ExcelPieceDto[] }>("/image-processor/excel/pieces", formData),
  excelPairs: (formData: FormData) =>
    apiForm<{ pairs: ExcelReplacementPairDto[] }>("/image-processor/excel/pairs", formData),
  runOcr: (formData: FormData) =>
    apiForm<OcrResultDto>("/image-processor/ocr", formData),
  replaceLine: (formData: FormData) =>
    apiForm<LineReplacementDto>("/image-processor/replace-line", formData),
  reapplyReplacements: (formData: FormData) =>
    apiForm<ReappliedReplacementsDto>("/image-processor/reapply-replacements", formData),
  inpaint: (formData: FormData) =>
    apiForm<{ edited_image: string }>("/image-processor/inpaint", formData),
};
