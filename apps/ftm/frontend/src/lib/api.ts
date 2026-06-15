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

export type KpiOut = {
  open_anomalies: number;
  anomalies_by_severity: Record<string, number>;
  anomalies_by_type: Record<string, number>;
  anomalies_by_status: Record<string, number>;
  resolution_rate: number;
  files_total: number;
  files_with_anomalies: number;
  avg_age_days: number;
  avg_resolution_days: number;
  top_files: Array<{ filename: string; count: number }>;
  top_rules: Array<{ rule: string; count: number }>;
};

export type ChatSession = {
  id: string;
  title: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  session_id: string;
  role: string;
  content: string;
  created_at: string;
};

export const resources = {
  projects: {
    list: () => api.get<Project[]>("/projects"),
    create: (body: { name: string; description: string; vision_enabled: boolean }) =>
      api.post<Project>("/projects", body),
    delete: (id: string) => api.delete<void>(`/projects/${id}`),
  },
  settings: {
    getMistral: () => api.get<MistralSettingsOut>("/settings/mistral"),
    updateMistral: (body: MistralSettingsIn) =>
      api.post<MistralSettingsOut>("/settings/mistral", body),
    testMistral: () => api.post<TestConnectionOut>("/settings/mistral/test"),
  },
  kpis: {
    global: () => api.get<KpiOut>("/kpis"),
  },
  chat: {
    sessions: () => api.get<ChatSession[]>("/chat/sessions"),
    messages: (sessionId: string) =>
      api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
    deleteSession: (sessionId: string) =>
      api.delete<void>(`/chat/sessions/${sessionId}`),
  },
};
