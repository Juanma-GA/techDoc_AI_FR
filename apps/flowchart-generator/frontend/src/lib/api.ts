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

export async function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw error ?? { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" };
  }
  return response;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await rawFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Message lisible pour une erreur API (format unifie) ou JS. */
export function errorText(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    const e = err as Partial<ApiError>;
    return e.request_id ? `${e.message} (${e.code}, ${e.request_id})` : String(e.message);
  }
  return String(err);
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
  demo_enabled: boolean;
};
export type SettingsInput = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  embed_model?: string;
  llm_enabled?: boolean;
  demo_enabled?: boolean;
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: SettingsInput) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};
