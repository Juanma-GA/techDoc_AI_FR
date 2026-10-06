/**
 * Typed fetch client for the doc-reviewer backend.
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

/**
 * En-tete anti-CSRF exige par le backend sur toute requete de modification
 * (cf. backend `core/request_guard.py`). Un en-tete personnalise force un
 * pre-vol CORS : un site tiers ne peut plus piloter l'API locale.
 */
export const CSRF_HEADERS: Readonly<Record<string, string>> = {
  "X-Requested-With": "doc-reviewer",
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...CSRF_HEADERS,
      ...(init.body !== undefined && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let payload: Partial<ApiErrorPayload> = {};
    try {
      payload = (await response.json()) as Partial<ApiErrorPayload>;
    } catch {
      // Server returned a non-JSON error.
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
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
};

export const API_BASE_URL = BASE_URL;

// ----- Health ---------------------------------------------------------------

export type LlmState = "ok" | "untested" | "not_configured" | "disabled";

export type HealthDto = {
  status: string;
  version: string;
  db: string;
  llm: LlmState;
};

export const healthApi = {
  read: () => api.get<HealthDto>("/health"),
};
