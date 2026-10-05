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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" };
  }
  return (await response.json()) as T;
}

// ----- Standard DTOs (STANDARD_POC.md - health/settings/admin) -------------

export type LlmStatus = "ok" | "disabled" | "not_configured" | "untested";
export type HealthDto = { status: string; version: string; db: string; llm: LlmStatus | string };

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  llm_enabled: boolean;
  llm_tested: boolean;
};
export type SettingsInput = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  embed_model?: string;
  llm_enabled?: boolean;
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: SettingsInput) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

export type TrackerField =
  | "reference"
  | "revision"
  | "subject"
  | "title"
  | "author"
  | "response_required"
  | "module_3_open_actions";

export type TrackerColumn = { name: string; index: number; field: TrackerField | null };
export type PreviewRecord = {
  source_path: string;
  file_name: string;
  reference: string;
  revision: string;
  subject: string;
  tracker_values: string[];
};
export type PreviewRequest = {
  source_path: string;
  tracker_path: string;
  sheet_name?: string;
  header_row?: number;
};
export type PreviewDto = {
  source_path: string;
  tracker_path: string;
  sheet_names: string[];
  sheet_name: string;
  header_row: number;
  columns: TrackerColumn[];
  records: PreviewRecord[];
};
export type ProcessRequest = {
  source_path: string;
  tracker_path: string;
  output_path: string;
  sheet_name: string;
  header_row: number;
  records: Pick<
    PreviewRecord,
    "source_path" | "reference" | "revision" | "subject" | "tracker_values"
  >[];
};
export type ProcessDto = {
  created_folders: string[];
  tracker_path: string;
  backup_path: string;
  rows_written: number;
};

export const ecmRenameApi = {
  preview: (body: PreviewRequest) =>
    api<PreviewDto>("/ecm-rename/preview", { method: "POST", body: JSON.stringify(body) }),
  process: (body: ProcessRequest) =>
    api<ProcessDto>("/ecm-rename/process", { method: "POST", body: JSON.stringify(body) }),
};
