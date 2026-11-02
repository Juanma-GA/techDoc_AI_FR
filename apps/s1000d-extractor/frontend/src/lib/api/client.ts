export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const requestIds = new WeakMap<Response, string>();

export type ApiError = { code: string; message: string; detail: unknown; request_id: string };

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId = "",
  ) {
    super(requestId ? `${message} [${requestId}]` : message);
    this.name = "ApiRequestError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function responseId(response: Response): string {
  return response.headers.get("X-Request-Id") ?? requestIds.get(response) ?? "";
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const requestId = crypto.randomUUID();
  const headers = new Headers(init.headers);
  headers.set("X-Request-Id", requestId);
  const method = (init.method ?? "GET").toUpperCase();
  if (method === "GET" || method === "HEAD" || init.body instanceof FormData) {
    headers.delete("Content-Type");
  } else if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiRequestError(0, "NETWORK_ERROR",
      error instanceof Error ? error.message : String(error), requestId);
  }
  requestIds.set(response, requestId);
  if (!response.ok) {
    let payload: unknown;
    if (response.headers.get("Content-Type")?.includes("json")) {
      try {
        payload = await response.json();
      } catch {
        throw new ApiRequestError(response.status, "INVALID_RESPONSE",
          "Invalid API error response.", responseId(response));
      }
    }
    throw new ApiRequestError(
      response.status,
      isRecord(payload) && typeof payload.code === "string" ? payload.code : "HTTP_ERROR",
      isRecord(payload) && typeof payload.message === "string" ? payload.message : response.statusText || `HTTP ${response.status}`,
      isRecord(payload) && typeof payload.request_id === "string" && payload.request_id
        ? payload.request_id : responseId(response),
    );
  }
  return response;
}

export async function readJson<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch {
    throw new ApiRequestError(response.status, "INVALID_RESPONSE",
      "Invalid API JSON response.", responseId(response));
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return readJson<T>(await request(path, init));
}

export function decodeResponse<T>(response: Response, parse: (value: unknown) => T, value: unknown): T {
  try {
    return parse(value);
  } catch (error) {
    throw new ApiRequestError(response.status, "INVALID_RESPONSE",
      error instanceof Error ? error.message : String(error), responseId(response));
  }
}

export async function apiValidated<T>(
  path: string, parse: (value: unknown) => T, init?: RequestInit,
): Promise<T> {
  const response = await request(path, init);
  return decodeResponse(response, parse, await readJson<unknown>(response));
}

export async function apiForm<T extends object>(
  path: string, form: FormData, parse?: (value: unknown) => T,
): Promise<T & { reused?: boolean }> {
  const response = await request(path, { method: "POST", body: form });
  const data = parse ? decodeResponse(response, parse, await readJson<unknown>(response))
    : await readJson<T>(response);
  return response.headers.get("X-Reused") === "true" ? { ...data, reused: true } : data;
}

export async function apiBlob(path: string, fallbackName = "download"): Promise<File> {
  const response = await request(path);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  let filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? fallbackName;
  try {
    if (encoded) filename = decodeURIComponent(encoded);
    return new File([await response.blob()], filename, {
      type: response.headers.get("Content-Type") ?? "application/octet-stream",
    });
  } catch (error) {
    throw new ApiRequestError(response.status, "RESPONSE_READ_FAILED",
      error instanceof Error ? error.message : String(error), responseId(response));
  }
}
