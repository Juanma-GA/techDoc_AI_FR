/**
 * Typed API client pour doc-writer. Reprend l'enveloppe d'erreur unifiée
 * du backend `{code, message, detail, request_id}`.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

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

export type DocumentContentDto = {
  id: string;
  filename: string;
  kind: DocumentKind;
  char_count: number;
  text: string;
};

export type ZoneDto = {
  id: string;
  kind: "placeholder" | "xxx" | "llm" | "frame";
  slide_index: number;
  slide_title: string;
  label: string;
  location: string;
  target: string;
  active: boolean;
  // Consignes libres pour le LLM de remplissage (format, ton, longueur...).
  instruction: string;
  // Alignement force du texte ecrit dans la zone (rendu PPTX). "" = auto
  // (preserve l'alignement du template).
  align: "" | "left" | "center" | "right" | "justify";
};

export type ZonesDto = {
  zones: ZoneDto[];
  // Zones soft-deleted, restaurables via documentsApi.restoreZone.
  removed: ZoneDto[];
  llm_used: boolean;
  // Zones LLM rejetees pour conflit de coherence (diagnostic).
  dropped_count: number;
  // Tant que false, l'export PPTX est refuse (ZONES_NOT_VALIDATED), sauf
  // auto-validation backend (dropped_count == 0 && zones > 0).
  validated: boolean;
};

// Structure geometrique d'un template PPTX (apercu de la modale d'export).
export type PptxBBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type PptxShape = {
  id: string;
  slide_index: number;
  slide_title: string;
  location: string;
  kind: string;
  text: string;
  bbox: PptxBBox | null;
};

export type PptxSlide = {
  index: number;
  title: string;
  shapes: PptxShape[];
};

export type PptxStructureDto = {
  slides: PptxSlide[];
  slide_width_emu: number;
  slide_height_emu: number;
};

// Apercu 'flux document' Word/PDF (pendant lineaire du SVG positionne PPTX).
export type FlowCellDto = {
  id: string;
  text: string;
  has_marker: boolean;
};

export type FlowBlockDto = {
  type: "paragraph" | "empty" | "table";
  id: string;
  location: string;
  text: string;
  has_marker: boolean;
  rows: FlowCellDto[][];
};

export type FlowDto = {
  blocks: FlowBlockDto[];
};

// Apercu du remplissage : zones (avec etat actif) + mapping zone_id -> contenu.
export type PreviewPptxDto = {
  zones: ZoneDto[];
  mapping: Record<string, string>;
};

export type RefillZonesDto = {
  mapping: Record<string, string>;
};

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
  // Modele vision (multimodal) pour lire les PDF (drapeaux, jauges...).
  vision_model: string;
  // Modele OCR document Mistral (/v1/ocr), repli de la vision.
  ocr_model: string;
  // Modele de transcription audio (Voxtral) pour la dictee vocale.
  transcribe_model: string;
  // Interrupteur LLM global (false = les taches IA sont sautees).
  llm_enabled: boolean;
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
  reparse: (id: string) =>
    request<DocumentDto>(`/documents/${id}/reparse`, { method: "POST" }),
  content: (id: string) =>
    request<DocumentContentDto>(`/documents/${id}/content`),
  zones: (id: string, refresh = false) =>
    request<ZonesDto>(
      `/documents/${id}/zones${refresh ? "?refresh=true" : ""}`,
    ),
  setZoneActive: (id: string, zoneId: string, active: boolean) =>
    request<ZonesDto>(`/documents/${id}/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),
  setZoneAlign: (id: string, zoneId: string, align: ZoneDto["align"]) =>
    request<ZonesDto>(`/documents/${id}/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify({ align }),
    }),
  deleteZone: (id: string, zoneId: string) =>
    request<ZonesDto>(`/documents/${id}/zones/${zoneId}`, {
      method: "DELETE",
    }),
  restoreZone: (id: string, zoneId: string) =>
    request<ZonesDto>(`/documents/${id}/zones/${zoneId}/restore`, {
      method: "POST",
    }),
  // Suppression groupee de zones (corbeille douce, restaurables).
  bulkDeleteZones: (id: string, ids: string[]) =>
    request<ZonesDto>(`/documents/${id}/zones/bulk-delete`, {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  // Edition du label / de la consigne (instruction) d'une zone, persistee sur
  // le template (relue par /refill-zones).
  updateZoneMeta: (
    id: string,
    zoneId: string,
    body: { label?: string; instruction?: string },
  ) =>
    request<ZonesDto>(`/documents/${id}/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  // Ajout d'une zone (transforme une shape libre en zone a remplir).
  addZone: (
    id: string,
    body: {
      target: string;
      label: string;
      slide_index: number;
      slide_title: string;
      location: string;
    },
  ) =>
    request<ZonesDto>(`/documents/${id}/zones`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // Structure geometrique du template (slides + shapes + bbox EMU), pour
  // l'apercu PPTX.
  structure: (id: string) =>
    request<PptxStructureDto>(`/documents/${id}/structure`),
  // Apercu 'flux document' Word/PDF (paragraphes + tableaux dans l'ordre).
  flow: (id: string) => request<FlowDto>(`/documents/${id}/flow`),
  validateZones: (id: string, validated: boolean) =>
    request<ZonesDto>(`/documents/${id}/zones/validate`, {
      method: "POST",
      body: JSON.stringify({ validated }),
    }),
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
  // Dictee vocale -> texte (Voxtral). Multipart : fetch direct (le helper
  // `request` force un Content-Type JSON incompatible avec FormData).
  transcribe: async (
    audio: Blob,
    filename = "dictation.webm",
  ): Promise<{ text: string; llm_used: boolean }> => {
    const form = new FormData();
    form.append("file", audio, filename);
    const response = await fetch(`${API_BASE}/sessions/transcribe`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      let payload: ApiError;
      try {
        payload = (await response.json()) as ApiError;
      } catch {
        payload = { code: "UNKNOWN", message: response.statusText, detail: null, request_id: "" };
      }
      throw new ApiClientError(payload, response.status);
    }
    return (await response.json()) as { text: string; llm_used: boolean };
  },
  create: (body: {
    title?: string;
    scope_doc_ids: string[];
    lang?: string;
    output_format?: string;
    length?: string;
    tone?: string;
    template_doc_id?: string | null;
    style_doc_id?: string | null;
  }) =>
    request<SessionDto>("/sessions", {
      method: "POST",
      body: JSON.stringify({ ...body, lang: body.lang ?? "fr" }),
    }),
  remove: (id: string) =>
    request<void>(`/sessions/${id}`, { method: "DELETE" }),
  messages: (id: string) =>
    request<MessageDto[]>(`/sessions/${id}/messages`),
  // Apercu du remplissage PPTX (zones + mapping propose) avant render.
  previewPptx: (id: string) =>
    request<PreviewPptxDto>(`/sessions/${id}/preview-pptx`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  // (Re)remplissage IA de zones precises. force=true relache la regle de
  // pertinence (remplit meme si la source est maigre).
  refillZones: (id: string, body: { zone_ids: string[]; force: boolean }) =>
    request<RefillZonesDto>(`/sessions/${id}/refill-zones`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // Render final du PPTX avec le mapping edite : declenche le download du blob.
  renderPptx: async (
    id: string,
    mapping: Record<string, string>,
    filename?: string | null,
  ): Promise<void> => {
    const response = await fetch(`${API_BASE}/sessions/${id}/render-pptx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mapping, filename: filename ?? null }),
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
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const m = /filename="?([^"]+)"?/.exec(disposition);
    const outName = m?.[1] ?? `${filename ?? id}.pptx`;
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objUrl;
    a.download = outName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objUrl);
  },
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
    const outName = m?.[1] ?? `${filename ?? "session"}.${format}`;
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

// ---------------------------------------------------------------------------
// Health (badge LLM sidebar)
// ---------------------------------------------------------------------------

// `llm` reflete l'etat runtime : "ok" (cle + active), "disabled" (interrupteur
// off), "not_configured" (pas de cle), "untested" (cle non encore testee).
export type LlmStatus = "ok" | "disabled" | "not_configured" | "untested";

export type HealthDto = {
  status: string;
  llm: LlmStatus | string;
};

export const healthApi = {
  read: () => request<HealthDto>("/health"),
};

// ---------------------------------------------------------------------------
// Admin (onglet Donnees : stats + reset)
// ---------------------------------------------------------------------------

export type AdminStatsDto = {
  documents: number;
  chunks: number;
  sessions: number;
  messages: number;
  total_size_bytes: number;
};

export type AdminResetScope = "documents" | "sessions" | "all";

export type AdminResetDto = { deleted: Record<string, number> };

export const adminApi = {
  stats: () => request<AdminStatsDto>("/admin/stats"),
  reset: (scope: AdminResetScope) =>
    request<AdminResetDto>(`/admin/reset/${scope}`, { method: "POST" }),
};

export const settingsApi = {
  read: () => request<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
    vision_model?: string;
    ocr_model?: string;
    transcribe_model?: string;
    llm_enabled?: boolean;
  }) =>
    request<SettingsDto>("/settings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  test: () =>
    request<TestConnectionDto>("/settings/test", { method: "POST" }),
};

// ---------------------------------------------------------------------------
// Prompts LLM editables runtime (/settings/prompts)
// ---------------------------------------------------------------------------

export type PromptEntryDto = { value: string; is_default: boolean };

export type PromptsDto = {
  pptx_analysis: PromptEntryDto;
  pptx_fill: PromptEntryDto;
};

export const promptsApi = {
  read: () => request<PromptsDto>("/settings/prompts"),
  // Chaque champ : undefined/null = inchange, chaine vide = reset au defaut.
  write: (body: { pptx_analysis?: string | null; pptx_fill?: string | null }) =>
    request<PromptsDto>("/settings/prompts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
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
