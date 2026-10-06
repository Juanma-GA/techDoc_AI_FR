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

export type AdminStatsDto = {
  documents: number;
  chunks: number;
  sessions: number;
  messages: number;
  total_size_bytes: number;
};

export type AdminResetDto = { scope: string; deleted: Record<string, number> };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  resetAll: () => api<AdminResetDto>("/admin/reset/all", { method: "POST" }),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: SettingsInput) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};
