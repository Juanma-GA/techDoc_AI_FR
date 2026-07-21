/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

// Surchargeable au build (VITE_API_BASE_URL) pour un deploiement en sous-chemin
// IIS (ex. /app/ocr-vision/api/v1). Defaut relatif '/api/v1' en local.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type ApiError = {
  code: string;
  message: string;
  detail: unknown;
  request_id: string;
};

export class ApiClientError extends Error {
  code: string;
  constructor(payload: ApiError) {
    super(payload.message);
    this.name = "ApiClientError";
    this.code = payload.code;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiClientError(
      error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" },
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// DTOs
// ---------------------------------------------------------------------------

export type LlmStatus = "ok" | "disabled" | "not_configured" | "untested";
export type HealthDto = { status: string; version: string; llm: LlmStatus | string };

export type AdminStatsDto = {
  projects: number;
  templates: number;
  tables: number;
  rows: number;
  images: number;
};
export type AdminResetDto = { deleted: Record<string, number> };

// ----- Capitalisation : templates / projets / tables / lignes --------------

export type ColumnType = "text" | "number" | "date" | "bool";
export type ColumnSpec = { key: string; label: string; type: ColumnType; rule: string };

export type TemplateDto = {
  id: string;
  name: string;
  description: string;
  columns: ColumnSpec[];
  created_at: string;
};
export type ProjectDto = { id: string; name: string; created_at: string };
export type ProjectTableDto = {
  id: string;
  project_id: string;
  template_id: string;
  name: string;
  columns: ColumnSpec[];
  row_count: number;
  created_at: string;
};
export type RowDto = {
  id: string;
  source_filename: string;
  values: Record<string, unknown>;
  created_at: string;
};
export type ExtractResultDto = {
  rows_added: number;
  rows: RowDto[];
  images_added: number;
  warning: string;
};
export type ImageDto = {
  id: string;
  source_filename: string;
  filename: string;
  page: number | null;
  url: string;
  created_at: string;
};
export type ExportFormat = "csv" | "xlsx";
export type ExportResultDto = { path: string; rows: number; format: string };

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  vision_model: string;
  llm_enabled: boolean;
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export type VisionResultDto = {
  ocr_text: string;
  description: string;
  warning?: string | null;
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const healthApi = {
  read: () => api<HealthDto>("/health"),
};

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  reset: (scope: "all") =>
    api<AdminResetDto>(`/admin/reset/${scope}`, { method: "POST" }),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
    vision_model?: string;
    llm_enabled?: boolean;
  }) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiClientError(
      error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" },
    );
  }
  return (await response.json()) as T;
}

export const visionApi = {
  // POST /vision/test (multipart) : { file, prompt? } -> { ocr_text, description }.
  test: (file: File, prompt?: string): Promise<VisionResultDto> => {
    const form = new FormData();
    form.append("file", file);
    if (prompt && prompt.trim()) form.append("prompt", prompt.trim());
    return postForm<VisionResultDto>("/vision/test", form);
  },
};

export const templatesApi = {
  list: () => api<TemplateDto[]>("/templates"),
  create: (body: { name: string; description: string; columns: ColumnSpec[] }) =>
    api<TemplateDto>("/templates", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: { name: string; description: string; columns: ColumnSpec[] }) =>
    api<TemplateDto>(`/templates/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/templates/${id}`, { method: "DELETE" }),
};

export const projectsApi = {
  list: () => api<ProjectDto[]>("/projects"),
  create: (name: string) =>
    api<ProjectDto>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  rename: (id: string, name: string) =>
    api<ProjectDto>(`/projects/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
  remove: (id: string) => api<void>(`/projects/${id}`, { method: "DELETE" }),
};

export const projectTablesApi = {
  list: (projectId?: string) =>
    api<ProjectTableDto[]>(
      `/project-tables${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`,
    ),
  create: (body: { project_id: string; template_id: string; name?: string }) =>
    api<ProjectTableDto>("/project-tables", { method: "POST", body: JSON.stringify(body) }),
  rename: (id: string, name: string) =>
    api<ProjectTableDto>(`/project-tables/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  get: (id: string) => api<ProjectTableDto>(`/project-tables/${id}`),
  remove: (id: string) => api<void>(`/project-tables/${id}`, { method: "DELETE" }),
  rows: (id: string) => api<RowDto[]>(`/project-tables/${id}/rows`),
};

export const rowsApi = {
  remove: (id: string) => api<void>(`/rows/${id}`, { method: "DELETE" }),
};

export const imagesApi = {
  list: (tableId: string) => api<ImageDto[]>(`/project-tables/${tableId}/images`),
  // URL absolue (relative a l'API base) servant le fichier JPG.
  fileUrl: (image: ImageDto) => `${API_BASE}${image.url.replace(/^\/api\/v1/, "")}`,
  remove: (id: string) => api<void>(`/images/${id}`, { method: "DELETE" }),
};

export const extractApi = {
  // POST /extract (multipart) : { file, project_table_id } -> lignes persistees.
  run: (projectTableId: string, file: File): Promise<ExtractResultDto> => {
    const form = new FormData();
    form.append("project_table_id", projectTableId);
    form.append("file", file);
    return postForm<ExtractResultDto>("/extract", form);
  },
  export: (projectTableId: string, targetDir: string, format: ExportFormat) =>
    api<ExportResultDto>("/export", {
      method: "POST",
      body: JSON.stringify({
        project_table_id: projectTableId,
        target_dir: targetDir,
        format,
      }),
    }),
};
