/**
 * Typed fetch client for the Corpus Agent backend.
 *
 * Mirrors the unified backend error format `{code, message, detail, request_id}`
 * (see docs/adr/0003-error-format.md) as `ApiClientError`. Namespaced clients
 * + SSE `streamAsk` — structure reprise de apps/doc-writer/frontend/src/lib/api.ts.
 * Les DTO vivent dans ./types.
 */

import type {
  AdminResetOut,
  AdminResetScope,
  AdminStatsOut,
  AnalysisRunOut,
  AnomalyOut,
  AnomalyStatus,
  ChatMessageOut,
  ChatSessionOut,
  FileOut,
  HealthResponse,
  I18nLangOut,
  I18nListOut,
  KpiOut,
  MistralSettingsIn,
  MistralSettingsOut,
  ProjectCreate,
  ProjectOut,
  ProjectUpdate,
  ReferenceMappingIn,
  ReferenceOut,
  RulesCatalogOut,
  RulesLegacyOut,
  SheetColumnOut,
  SheetPreviewOut,
  TestConnectionOut,
  UploadResult,
} from "./types";

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

  constructor(status: number, code: string, message: string, detail: unknown, requestId: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.requestId = requestId;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function toError(response: Response): Promise<ApiClientError> {
  let payload: Partial<ApiErrorPayload> = {};
  try {
    payload = (await response.json()) as Partial<ApiErrorPayload>;
  } catch {
    /* non-JSON error (proxy failure) */
  }
  return new ApiClientError(
    response.status,
    payload.code ?? `HTTP_${response.status}`,
    payload.message ?? response.statusText ?? "Request failed",
    payload.detail ?? null,
    payload.request_id ?? response.headers.get("X-Request-Id") ?? "",
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body !== undefined && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init.headers,
    },
  });
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

async function uploadForm<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body: form });
}

async function downloadBlob(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${BASE_URL}${path}`, { method: "GET" });
  if (!response.ok) throw await toError(response);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const m = /filename="?([^"]+)"?/.exec(disposition);
  const outName = m?.[1] ?? fallbackName;
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = outName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}

// --- Clients ----------------------------------------------------------------

export const healthApi = { read: () => api.get<HealthResponse>("/health") };

export const i18nApi = {
  lang: (lng: string) => api.get<I18nLangOut>(`/i18n/${lng}`),
  available: () => api.get<I18nListOut>("/i18n"),
};

export const projectsApi = {
  list: () => api.get<ProjectOut[]>("/projects"),
  get: (id: string) => api.get<ProjectOut>(`/projects/${id}`),
  create: (body: ProjectCreate) => api.post<ProjectOut>("/projects", body),
  update: (id: string, body: ProjectUpdate) => api.put<ProjectOut>(`/projects/${id}`, body),
  remove: (id: string) => api.delete<void>(`/projects/${id}`),
};

export const filesApi = {
  list: (pid: string) => api.get<FileOut[]>(`/projects/${pid}/files`),
  upload: (pid: string, files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return uploadForm<UploadResult>(`/projects/${pid}/files`, form);
  },
  remove: (pid: string, fileId: string) =>
    api.delete<void>(`/projects/${pid}/files/${fileId}`),
};

export const referenceApi = {
  get: (pid: string) => api.get<ReferenceOut>(`/projects/${pid}/reference`),
  upload: (pid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return uploadForm<ReferenceOut>(`/projects/${pid}/reference`, form);
  },
  remove: (pid: string) => api.delete<void>(`/projects/${pid}/reference`),
  columns: (pid: string, sheet: string, headerRow?: number) => {
    const qs = new URLSearchParams({ sheet });
    if (headerRow) qs.set("header_row", String(headerRow));
    return api.get<SheetColumnOut[]>(`/projects/${pid}/reference/columns?${qs}`);
  },
  preview: (pid: string, sheet: string) =>
    api.get<SheetPreviewOut>(`/projects/${pid}/reference/preview?sheet=${encodeURIComponent(sheet)}`),
  saveMapping: (pid: string, body: ReferenceMappingIn) =>
    api.put<ReferenceOut>(`/projects/${pid}/reference/mapping`, body),
  basl: (pid: string) => api.get<ReferenceOut>(`/projects/${pid}/basl`),
  uploadBasl: (pid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return uploadForm<ReferenceOut>(`/projects/${pid}/basl`, form);
  },
  baslColumns: (pid: string, sheet: string, headerRow?: number) => {
    const qs = new URLSearchParams({ sheet });
    if (headerRow) qs.set("header_row", String(headerRow));
    return api.get<SheetColumnOut[]>(`/projects/${pid}/basl/columns?${qs}`);
  },
  baslPreview: (pid: string, sheet: string) =>
    api.get<SheetPreviewOut>(`/projects/${pid}/basl/preview?sheet=${encodeURIComponent(sheet)}`),
  saveBaslMapping: (pid: string, body: ReferenceMappingIn) =>
    api.put<ReferenceOut>(`/projects/${pid}/basl/mapping`, body),
};

export const analysisApi = {
  run: (pid: string) => api.post<AnalysisRunOut>(`/projects/${pid}/analysis/run`),
  reset: (pid: string) => api.delete<void>(`/projects/${pid}/analysis/reset`),
};

export const anomaliesApi = {
  list: (pid: string) => api.get<AnomalyOut[]>(`/projects/${pid}/anomalies`),
  setStatus: (id: string, status: AnomalyStatus) =>
    api.patch<AnomalyOut>(`/anomalies/${id}`, { status }),
  bulkStatus: (ids: string[], status: AnomalyStatus) =>
    api.post<{ updated: number; status: string }>("/anomalies/bulk-status", { ids, status }),
  exportCsv: (pid: string) =>
    downloadBlob(`/projects/${pid}/anomalies/export.csv`, `anomalies-${pid}.csv`),
};

export const kpisApi = {
  scope: (ids: string[]) => {
    const qs = ids.length ? `?project_ids=${ids.join(",")}` : "";
    return api.get<KpiOut>(`/kpis${qs}`);
  },
};

export const adminApi = {
  stats: () => api.get<AdminStatsOut>("/admin/stats"),
  reset: (scope: AdminResetScope) => api.post<AdminResetOut>("/admin/reset", { scope }),
};

export const settingsApi = {
  read: () => api.get<MistralSettingsOut>("/settings/mistral"),
  write: (body: MistralSettingsIn) => api.post<MistralSettingsOut>("/settings/mistral", body),
  test: () => api.post<TestConnectionOut>("/settings/mistral/test"),
  rulesCatalog: () => api.get<RulesCatalogOut>("/settings/rules/catalog"),
  rulesLegacy: () => api.get<RulesLegacyOut>("/settings/rules"),
};

export const chatApi = {
  sessions: () => api.get<ChatSessionOut[]>("/chat/sessions"),
  messages: (sid: string) => api.get<ChatMessageOut[]>(`/chat/sessions/${sid}/messages`),
  removeSession: (sid: string) => api.delete<void>(`/chat/sessions/${sid}`),
};

// --- SSE streaming (POST /chat/ask) -----------------------------------------

export type ChatStreamHandlers = {
  onSession?: (info: { session_id: string; title?: string }) => void;
  onToken?: (delta: string) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
};

/**
 * Consomme l'endpoint SSE POST /chat/ask via fetch + ReadableStream
 * (EventSource natif ne supporte pas POST). Retourne une fonction d'annulation.
 */
// Timeout d'inactivite du flux SSE (ms). Si aucune donnee n'arrive dans cet
// intervalle, on annule la requete pour ne pas laisser l'UI bloquee
// indefiniment sur un flux suspendu. Configurable via .env (VITE_SSE_IDLE_TIMEOUT_MS).
const SSE_IDLE_TIMEOUT_MS = Number(import.meta.env.VITE_SSE_IDLE_TIMEOUT_MS) || 60_000;

export function streamAsk(
  body: { session_id: string | null; project_ids: string[]; question: string; lang: string },
  handlers: ChatStreamHandlers,
): () => void {
  const controller = new AbortController();
  // Annulation par timeout : on distingue l'abort manuel (cleanup) de l'abort
  // par inactivite pour pouvoir remonter une erreur explicite dans le 2e cas.
  let timedOut = false;
  let idleTimer: ReturnType<typeof setTimeout> | undefined;
  const armIdleTimeout = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, SSE_IDLE_TIMEOUT_MS);
  };
  const clearIdleTimeout = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = undefined;
  };

  void (async () => {
    let response: Response;
    try {
      armIdleTimeout();
      response = await fetch(`${BASE_URL}/chat/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      clearIdleTimeout();
      if (timedOut) {
        handlers.onError?.("Le flux a expire (aucune reponse du serveur).");
        return;
      }
      if (controller.signal.aborted) return;
      handlers.onError?.(err instanceof Error ? err.message : String(err));
      return;
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const payload = (await response.json()) as ApiErrorPayload;
        detail = payload.message || detail;
      } catch {
        /* noop */
      }
      handlers.onError?.(detail);
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) {
      handlers.onError?.("Aucun flux disponible");
      return;
    }
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        armIdleTimeout(); // donnees recues -> on repousse le timeout d'inactivite
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let sep;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          processChunk(chunk, handlers);
        }
      }
    } catch (err) {
      if (timedOut) {
        handlers.onError?.("Le flux a expire (aucune donnee recue).");
      } else if (!controller.signal.aborted) {
        handlers.onError?.(err instanceof Error ? err.message : String(err));
      }
    } finally {
      clearIdleTimeout();
    }
  })();
  return () => {
    clearIdleTimeout();
    controller.abort();
  };
}

function processChunk(chunk: string, handlers: ChatStreamHandlers) {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  const data = dataLines.join("\n");
  if (event === "session") {
    try {
      handlers.onSession?.(JSON.parse(data) as { session_id: string; title?: string });
    } catch {
      /* noop */
    }
  } else if (event === "token") {
    handlers.onToken?.(data);
  } else if (event === "done") {
    handlers.onDone?.();
  } else if (event === "error") {
    let msg = data;
    try {
      msg = (JSON.parse(data) as { message?: string }).message ?? data;
    } catch {
      /* noop */
    }
    handlers.onError?.(msg);
  }
}
