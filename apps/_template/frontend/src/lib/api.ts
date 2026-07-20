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
