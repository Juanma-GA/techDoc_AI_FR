/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

const API_BASE = "/api/v1";

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
  documents: number;
  chunks: number;
  sessions: number;
  messages: number;
  total_size_bytes: number;
};
export type AdminResetDto = { deleted: Record<string, number> };

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

export const visionApi = {
  // POST /vision/test (multipart) : { file, prompt? } -> { ocr_text, description }.
  test: async (file: File, prompt?: string): Promise<VisionResultDto> => {
    const form = new FormData();
    form.append("file", file);
    if (prompt && prompt.trim()) form.append("prompt", prompt.trim());
    const response = await fetch(`${API_BASE}/vision/test`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => null)) as ApiError | null;
      throw new ApiClientError(
        error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" },
      );
    }
    return (await response.json()) as VisionResultDto;
  },
};
