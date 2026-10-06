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
export type CreateFoldersRequest = {
  source_path: string;
  output_path: string;
  records: Pick<PreviewRecord, "source_path" | "reference" | "revision" | "subject">[];
};
export type CreateFoldersDto = {
  created_folders: string[];
};
export type AppendTrackerRequest = {
  tracker_path: string;
  sheet_name: string;
  header_row: number;
  records: Pick<PreviewRecord, "tracker_values">[];
};
export type AppendTrackerDto = {
  tracker_path: string;
  rows_written: number;
};

export type BrowseKind = "source_file" | "source_directory" | "tracker_file" | "output_directory";
export type BrowseRequest = {
  kind: BrowseKind;
  current_path?: string;
  language: "fr" | "en";
};
export type BrowseResponse = { path: string | null };
export type PathPreferencesDto = {
  source_path: string;
  tracker_path: string;
  output_path: string;
};

export const ecmRenameApi = {
  getPathPreferences: () => api<PathPreferencesDto>("/ecm-rename/paths"),
  savePathPreferences: (body: PathPreferencesDto) =>
    api<PathPreferencesDto>("/ecm-rename/paths", { method: "PUT", body: JSON.stringify(body) }),
  browse: (body: BrowseRequest) =>
    api<BrowseResponse>("/ecm-rename/browse", { method: "POST", body: JSON.stringify(body) }),
  preview: (body: PreviewRequest) =>
    api<PreviewDto>("/ecm-rename/preview", { method: "POST", body: JSON.stringify(body) }),
  createFolders: (body: CreateFoldersRequest) =>
    api<CreateFoldersDto>("/ecm-rename/folders", { method: "POST", body: JSON.stringify(body) }),
  appendTracker: (body: AppendTrackerRequest) =>
    api<AppendTrackerDto>("/ecm-rename/tracker", { method: "POST", body: JSON.stringify(body) }),
};
