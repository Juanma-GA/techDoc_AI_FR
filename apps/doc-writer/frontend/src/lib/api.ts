/**
 * Typed API client pour doc-writer. Reprend l'enveloppe d'erreur unifiée
 * du backend `{code, message, detail, request_id}`.
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
  detail: unknown;
  requestId: string;
  status: number;

  constructor(payload: ApiError, status: number) {
    super(payload.message);
    this.name = "ApiClientError";
    this.code = payload.code;
    this.detail = payload.detail;
    this.requestId = payload.request_id;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    let payload: ApiError;
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      payload = {
        code: "UNKNOWN",
        message: response.statusText,
        detail: null,
        request_id: "",
      };
    }
    throw new ApiClientError(payload, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Types DTO
// ---------------------------------------------------------------------------

export type DocumentKind = "source" | "template" | "style";

export type DocumentDto = {
  id: string;
  filename: string;
  mime_type: string;
  size: number;
  sha256: string;
  chunk_count: number;
  index_error: string | null;
  kind: DocumentKind;
  uploaded_at: string;
};

export type ZoneDto = {
  id: string;
  kind: "placeholder" | "xxx" | "llm";
  slide_index: number;
  slide_title: string;
  label: string;
  location: string;
  target: string;
};

export type ZonesDto = { zones: ZoneDto[]; llm_used: boolean };

export type UploadItemResult = {
  filename: string;
  ok: boolean;
  document_id?: string;
  skipped?: string;
  error?: string;
  chunk_count?: number;
};

export type UploadResult = { uploaded: UploadItemResult[] };

export type SessionDto = {
  id: string;
  title: string;
  scope_doc_ids: string[];
  lang: string;
  template_doc_id: string | null;
  created_at: string;
};

export type Citation = {
  chunk_id: string;
  filename: string;
  score: number;
};

export type MessageDto = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | string;
  content: string;
  citations: Citation[];
  created_at: string;
};

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
};

export type TestConnectionDto = {
  ok: boolean;
  models: string[];
  error?: string | null;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export const documentsApi = {
  list: (kind?: DocumentKind) => {
    const qs = kind ? `?kind=${kind}` : "";
    return request<DocumentDto[]>(`/documents${qs}`);
  },
  remove: (id: string) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),
  zones: (id: string, refresh = false) =>
    request<ZonesDto>(
      `/documents/${id}/zones${refresh ? "?refresh=true" : ""}`,
    ),
  upload: async (
    files: File[],
    kind: DocumentKind = "source",
  ): Promise<UploadResult> => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("kind", kind);
    const response = await fetch(`${API_BASE}/documents`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      let payload: ApiError;
      try {
        payload = (await response.json()) as ApiError;
      } catch {
        payload = {
          code: "UNKNOWN",
          message: response.statusText,
          detail: null,
          request_id: "",
        };
      }
      throw new ApiClientError(payload, response.status);
    }
    return (await response.json()) as UploadResult;
  },
};

export type ExportFormat = "md" | "docx" | "pdf" | "pptx";

export const sessionsApi = {
  list: () => request<SessionDto[]>("/sessions"),
  create: (body: {
    title?: string;
    scope_doc_ids: string[];
    lang?: string;
    template_doc_id?: string | null;
  }) =>
    request<SessionDto>("/sessions", {
      method: "POST",
      body: JSON.stringify({ ...body, lang: body.lang ?? "fr" }),
    }),
  remove: (id: string) =>
    request<void>(`/sessions/${id}`, { method: "DELETE" }),
  messages: (id: string) =>
    request<MessageDto[]>(`/sessions/${id}/messages`),
  exportUrl: (id: string, format: ExportFormat, filename?: string): string => {
    const qs = new URLSearchParams({ format });
    if (filename) qs.set("filename", filename);
    return `${API_BASE}/sessions/${id}/export?${qs.toString()}`;
  },
  download: async (
    id: string,
    format: ExportFormat,
    filename?: string,
  ): Promise<void> => {
    const url = sessionsApi.exportUrl(id, format, filename);
    const response = await fetch(url, { method: "GET" });
    if (!response.ok) {
      let payload: ApiError;
      try {
        payload = (await response.json()) as ApiError;
      } catch {
        payload = {
          code: "UNKNOWN",
          message: response.statusText,
          detail: null,
          request_id: "",
        };
      }
      throw new ApiClientError(payload, response.status);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const m = /filename="?([^"]+)"?/.exec(disposition);
    const outName = m ? m[1] : `${filename ?? "session"}.${format}`;
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objUrl;
    a.download = outName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objUrl);
  },
};

export const settingsApi = {
  read: () => request<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
  }) =>
    request<SettingsDto>("/settings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  test: () =>
    request<TestConnectionDto>("/settings/test", { method: "POST" }),
};

// ---------------------------------------------------------------------------
// SSE streaming
// ---------------------------------------------------------------------------

export type StreamHandlers = {
  onSession?: (info: { session_id: string; title: string }) => void;
  onToken?: (delta: string) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
};

/**
 * Consomme l'endpoint SSE POST `/sessions/{id}/ask` via fetch + ReadableStream
 * (l'EventSource natif ne supporte pas POST). Retourne une fonction d'annulation.
 */
export function streamAsk(
  sessionId: string,
  question: string,
  handlers: StreamHandlers,
): () => void {
  const controller = new AbortController();
  void (async () => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/sessions/${sessionId}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      handlers.onError?.(err instanceof Error ? err.message : String(err));
      return;
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as ApiError;
        detail = body.message || detail;
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
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        // Normalize CRLF -> LF : sse-starlette emits "\r\n\r\n", we look for "\n\n".
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let sepIdx;
        while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          processChunk(chunk, handlers);
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        handlers.onError?.(err instanceof Error ? err.message : String(err));
      }
    }
  })();

  return () => controller.abort();
}

function processChunk(chunk: string, handlers: StreamHandlers) {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  const data = dataLines.join("\n");
  if (event === "session") {
    try {
      const parsed = JSON.parse(data) as { session_id: string; title: string };
      handlers.onSession?.(parsed);
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
      const parsed = JSON.parse(data) as { message?: string };
      msg = parsed.message ?? data;
    } catch {
      /* noop */
    }
    handlers.onError?.(msg);
  }
}
