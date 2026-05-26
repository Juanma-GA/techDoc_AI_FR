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
