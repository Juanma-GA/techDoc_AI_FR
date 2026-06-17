/**
 * Typed fetch client for the FTM v3 backend.
 *
 * Mirrors the unified backend error format `{code, message, detail, request_id}`
 * (see docs/adr/0003-error-format.md). Surfaces it as `ApiClientError` so the
 * UI can react on the stable `code` rather than parsing strings.
 */

export type ApiErrorPayload = {
  code: string;
  message: string;
  detail: unknown;
  request_id: string;
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;
  readonly requestId: string;

  constructor(
    status: number,
    code: string,
    message: string,
    detail: unknown,
    requestId: string,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.requestId = requestId;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function requestFormData<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: formData,
  });
  if (!response.ok) {
    let payload: Partial<ApiErrorPayload> = {};
    try { payload = (await response.json()) as Partial<ApiErrorPayload>; } catch { /* noop */ }
    throw new ApiClientError(
      response.status,
      payload.code ?? `HTTP_${response.status}`,
      payload.message ?? response.statusText ?? "Request failed",
      payload.detail ?? null,
      payload.request_id ?? response.headers.get("X-Request-Id") ?? "",
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let payload: Partial<ApiErrorPayload> = {};
    try {
      payload = (await response.json()) as Partial<ApiErrorPayload>;
    } catch {
      // Server returned a non-JSON error (e.g. proxy failure).
    }
    throw new ApiClientError(
      response.status,
      payload.code ?? `HTTP_${response.status}`,
      payload.message ?? response.statusText ?? "Request failed",
      payload.detail ?? null,
      payload.request_id ?? response.headers.get("X-Request-Id") ?? "",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  db: string;
  llm: "configured" | "not_configured";
};

export type Project = {
  id: string;
  name: string;
  description: string;
  vision_enabled: boolean;
  created_at: string;
};

export type ProjectUpdate = {
  name?: string;
  description?: string;
  vision_enabled?: boolean;
};

export type FileVersionOut = {
  id: string;
  filename: string;
  sha256: string;
  size: number;
  uploaded_at: string;
};

export type FileOut = {
  id: string;
  current_name: string;
  mime_type: string;
  created_at: string;
  versions: FileVersionOut[];
};

export type UploadResultItem = {
  filename: string;
  ok: boolean;
  sha256?: string;
  size?: number;
  skipped?: string;
  error?: string;
};

export type UploadResultOut = {
  uploaded: UploadResultItem[];
};

export type ReferenceColumnDef = {
  name: string;
  sheet: string;
  column: string;
  builtin: boolean;
};

export type ReferenceOut = {
  path: string | null;
  sheets: string[];
  columns: ReferenceColumnDef[];
};

export type SheetColumnOut = {
  letter: string;
  header: string;
};

export type ReferenceMappingIn = {
  columns: Array<{ name: string; sheet: string; column: string }>;
};

export type AnalysisRunOut = {
  id: string;
  project_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  summary: string;
};

export type MistralSettingsOut = {
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  chat_model: string;
  embed_model: string;
  vision_model: string;
};

export type MistralSettingsIn = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  embed_model?: string;
  vision_model?: string;
};

export type TestConnectionOut = {
  ok: boolean;
  message: string;
  models: string[];
};

/**
 * Point de la serie temporelle : un run d'analyse, avec son total et un
 * compteur par type d'anomalie (cf. ANOMALY_TYPES backend). L'index signature
 * couvre les ~17 cles de type ; run_id/started_at sont des string.
 */
export type KpiOverTimePoint = {
  run_id: string;
  started_at: string;
  total: number;
  [anomalyType: string]: number | string;
};

export type KpiOut = {
  open_anomalies: number;
  anomalies_by_severity: Record<string, number>;
  anomalies_by_type: Record<string, number>;
  anomalies_by_status: Record<string, number>;
  anomalies_by_confidence: Record<string, number>;
  anomalies_over_time: KpiOverTimePoint[];
  resolution_rate: number;
  files_total: number;
  files_with_anomalies: number;
  avg_age_days: number;
  avg_resolution_days: number;
  top_files: Array<{ filename: string; count: number }>;
  top_rules: Array<{ rule: string; count: number }>;
};

export type AnomalyOut = {
  id: string;
  project_id: string;
  file_version_id: string | null;
  type: string;
  severity: string;
  confidence: string;
  message: string;
  suggestion: string;
  message_key: string | null;
  message_params_json: string | null;
  suggestion_key: string | null;
  suggestion_params_json: string | null;
  location: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
};

export type AnomalyBulkStatusIn = {
  ids: string[];
  status: string;
};

export type AnomalyBulkStatusOut = {
  updated: number;
  status: string;
};

export type ChatSession = {
  id: string;
  title: string;
  created_at: string;
  scope_project_ids: string[];
};

export type ChatMessage = {
  id: string;
  session_id: string;
  role: string;
  content: string;
  created_at: string;
};

export type AdminStatsOut = {
  projects: number;
  files: number;
  file_versions: number;
  anomalies: number;
  analysis_runs: number;
  chat_sessions: number;
  chat_messages: number;
  document_chunks: number;
  storage_bytes: number;
  db_bytes: number;
};

export type AdminResetIn = {
  scope: "analyses" | "chat" | "all";
};

export type AdminResetOut = {
  scope: string;
  deleted: Record<string, number>;
};

export type RuleParamSpec = {
  type: string;
  default: unknown;
  name_key: string;
  constraints: Record<string, unknown>;
};

export type RuleExample = {
  text: string;
  valid: boolean;
  note_key?: string | null;
};

export type CatalogRule = {
  id: string;
  family: string;
  name_key: string;
  description_key: string;
  severity: string;
  enabled_default: boolean;
  params: Record<string, RuleParamSpec>;
  examples: RuleExample[];
  anomaly_types: string[];
  requires: string[];
};

export type ResolvedRule = {
  id: string;
  enabled: boolean;
  params: Record<string, unknown>;
  runnable: boolean;
};

export type RulesCatalogOut = {
  rules: CatalogRule[];
  resolved: ResolvedRule[];
  capabilities: string[];
};

export type CustomRule = {
  id: string;
  label: string;
  consigne: string;
  severity: string;
};

export type LegacyRulesOut = {
  rules: {
    regles_personnalisees?: CustomRule[];
    instructions_libres?: string;
    [key: string]: unknown;
  };
  overridden: boolean;
  editable: boolean;
};

export const resources = {
  projects: {
    list: () => api.get<Project[]>("/projects"),
    get: (id: string) => api.get<Project>(`/projects/${id}`),
    create: (body: { name: string; description: string; vision_enabled: boolean }) =>
      api.post<Project>("/projects", body),
    update: (id: string, body: ProjectUpdate) => api.put<Project>(`/projects/${id}`, body),
    delete: (id: string) => api.delete<void>(`/projects/${id}`),
  },
  files: {
    list: (pid: string) => api.get<FileOut[]>(`/projects/${pid}/files`),
    upload: (pid: string, formData: FormData) =>
      requestFormData<UploadResultOut>(`/projects/${pid}/files`, formData),
    delete: (pid: string, fid: string) => api.delete<void>(`/projects/${pid}/files/${fid}`),
  },
  reference: {
    get: (pid: string) => api.get<ReferenceOut>(`/projects/${pid}/reference`),
    upload: (pid: string, formData: FormData) =>
      requestFormData<ReferenceOut>(`/projects/${pid}/reference`, formData),
    getColumns: (pid: string, sheet: string) =>
      api.get<SheetColumnOut[]>(
        `/projects/${pid}/reference/columns?sheet=${encodeURIComponent(sheet)}`,
      ),
    updateMapping: (pid: string, body: ReferenceMappingIn) =>
      api.put<ReferenceOut>(`/projects/${pid}/reference/mapping`, body),
    delete: (pid: string) => api.delete<void>(`/projects/${pid}/reference`),
  },
  basl: {
    get: (pid: string) => api.get<ReferenceOut>(`/projects/${pid}/basl`),
    upload: (pid: string, formData: FormData) =>
      requestFormData<ReferenceOut>(`/projects/${pid}/basl`, formData),
    delete: (pid: string) => api.delete<void>(`/projects/${pid}/basl`),
  },
  analysis: {
    run: (pid: string) => api.post<AnalysisRunOut>(`/projects/${pid}/analysis/run`),
    reset: (pid: string) => api.delete<void>(`/projects/${pid}/analysis/reset`),
  },
  settings: {
    getMistral: () => api.get<MistralSettingsOut>("/settings/mistral"),
    updateMistral: (body: MistralSettingsIn) =>
      api.post<MistralSettingsOut>("/settings/mistral", body),
    testMistral: () => api.post<TestConnectionOut>("/settings/mistral/test"),
    getCatalog: () => api.get<RulesCatalogOut>("/settings/rules/catalog"),
    getLegacyRules: () => api.get<LegacyRulesOut>("/settings/rules"),
  },
  kpis: {
    global: () => api.get<KpiOut>("/kpis"),
    /** Perimetre multi-projets : `ids` vide => tous les projets. */
    byScope: (ids: string[]) =>
      api.get<KpiOut>(ids.length ? `/kpis?project_ids=${ids.join(",")}` : "/kpis"),
  },
  anomalies: {
    list: (pid: string) => api.get<AnomalyOut[]>(`/projects/${pid}/anomalies`),
    updateStatus: (id: string, status: string) =>
      api.patch<AnomalyOut>(`/anomalies/${id}`, { status }),
    bulkStatus: (body: AnomalyBulkStatusIn) =>
      api.post<AnomalyBulkStatusOut>("/anomalies/bulk-status", body),
    exportCsvUrl: (pid: string) => `${BASE_URL}/projects/${pid}/anomalies/export.csv`,
  },
  chat: {
    sessions: () => api.get<ChatSession[]>("/chat/sessions"),
    messages: (sessionId: string) =>
      api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
    deleteSession: (sessionId: string) =>
      api.delete<void>(`/chat/sessions/${sessionId}`),
  },
  admin: {
    stats: () => api.get<AdminStatsOut>("/admin/stats"),
    reset: (body: AdminResetIn) => api.post<AdminResetOut>("/admin/reset", body),
  },
};
