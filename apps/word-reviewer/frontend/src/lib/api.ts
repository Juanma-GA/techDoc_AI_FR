/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

// Surchargeable au build (VITE_API_BASE_URL) pour un deploiement en sous-chemin
// IIS (ex. /app/word-reviewer/api/v1). Defaut relatif '/api/v1' en local.
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
    const e = (await response.json().catch(() => null)) as ApiError | null;
    throw new Error(e?.message || response.statusText || "Erreur");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ----- Standard DTOs --------------------------------------------------------

export type LlmStatus = "ok" | "disabled" | "not_configured" | "untested";
export type HealthDto = { status: string; version: string; llm: LlmStatus | string };

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  llm_enabled: boolean;
  llm_confidence_threshold: number;
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
    llm_enabled?: boolean;
    llm_confidence_threshold?: number;
  }) => api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

// ----- Admin / dashboard / metrics ------------------------------------------

export type DashboardDto = {
  documents: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  by_kind: Record<string, number>;
  top_documents: { id: string; original_filename: string; open_count: number }[];
};
export type StatsDto = {
  documents: number;
  batches: number;
  suggestions: number;
  rules: number;
  standards: number;
};
export type MetricsDto = {
  rules: {
    rule_code: string;
    total: number;
    accepted: number;
    rejected: number;
    acceptance_rate: number;
  }[];
};

export const adminApi = {
  dashboard: () => api<DashboardDto>("/admin/dashboard"),
  stats: () => api<StatsDto>("/admin/stats"),
  metrics: () => api<MetricsDto>("/metrics"),
  reset: (scope: "all" | "rules") =>
    api<{ deleted?: Record<string, number> }>(`/admin/reset/${scope}`, { method: "POST" }),
};

// ----- Documents ------------------------------------------------------------

export type WordDoc = {
  id: string;
  original_filename: string;
  status: string;
  findings_total: number;
  findings_open: number;
  block_count: number;
  current_version: number;
};

export type DocBlock = {
  target_id: string;
  kind: string;
  zone?: string;
  semantic_zone?: string;
  text: string;
  heading_level?: number;
  table_id?: number | null;
  row?: number;
  col?: number;
  page?: number;
};
export type DocView = {
  original_filename: string;
  current_version: number;
  blocks: DocBlock[];
};

export type PdfBox = { left: number; top: number; width: number; height: number };
export type PdfHighlight = { id: string; page: number; boxes: PdfBox[] };
export type PdfView = { available: boolean; page_count: number; highlights: PdfHighlight[] };

export type LayoutFinding = {
  id: string;
  rule_code: string;
  severity: string;
  message: string;
  page: number;
  boxes: PdfBox[];
};
export type LayoutChecks = { available: boolean; findings: LayoutFinding[] };

export type Suggestion = {
  id: string;
  target_id: string;
  rule_code: string;
  severity: string;
  status: string;
  message: string;
  original_text: string;
  proposed_text: string;
  char_start: number;
  char_end: number;
  applied_version?: number | null;
};

export const documentsApi = {
  list: () => api<WordDoc[]>("/documents"),
  get: (id: string) => api<WordDoc>(`/documents/${id}`),
  remove: (id: string) => api<void>(`/documents/${id}`, { method: "DELETE" }),
  view: (id: string) => api<DocView>(`/documents/${id}/view`),
  pdfView: (id: string) => api<PdfView>(`/documents/${id}/pdf-view`),
  layoutChecks: (id: string) => api<LayoutChecks>(`/documents/${id}/layout-checks`),
  pageImageUrl: (id: string, page: number, dpi = 130) =>
    `${API_BASE}/documents/${id}/pages/${page}.png?dpi=${dpi}`,
  suggestions: (id: string) => api<Suggestion[]>(`/documents/${id}/suggestions`),
  exportUrl: (id: string) => `${API_BASE}/documents/${id}/export`,
  upload: async (
    files: File[],
  ): Promise<{ documents: { id: string }[]; ignored?: string[] }> => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    const res = await fetch(`${API_BASE}/documents`, { method: "POST", body: fd });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as { documents: { id: string }[]; ignored?: string[] };
  },
  exportZip: async (ids: string[]): Promise<void> => {
    const res = await fetch(`${API_BASE}/documents/export-zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: ids }),
    });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "word-reviewer-export.zip";
    a.click();
    URL.revokeObjectURL(a.href);
  },
};

/**
 * Lance l'analyse d'un document et consomme le flux SSE (progress / suggestion /
 * error). `onEvent(event, data)`. Résout quand le flux se termine.
 */
export async function analyzeStream(
  docId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true }).replace(/\r/g, "");
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      let parsed: Record<string, unknown> = {};
      try {
        parsed = data ? (JSON.parse(data) as Record<string, unknown>) : {};
      } catch {
        /* ignore */
      }
      onEvent(event, parsed);
    }
  }
}

// ----- Suggestions ----------------------------------------------------------

export const suggestionsApi = {
  patch: (id: string, body: Partial<Pick<Suggestion, "status" | "proposed_text">>) =>
    api<Suggestion>(`/suggestions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  apply: (id: string) => api<unknown>(`/suggestions/${id}/apply`, { method: "POST" }),
  applyGroup: (id: string) => api<unknown>(`/suggestions/${id}/apply-group`, { method: "POST" }),
  undo: (id: string) => api<unknown>(`/suggestions/${id}/undo`, { method: "POST" }),
};

// ----- Rules / standards ----------------------------------------------------

export type CatalogRule = {
  code: string;
  title?: string;
  kind: string;
  severity: string;
  pattern?: string;
  replacement?: string;
  message?: string;
  source?: string;
  metadata?: { zone?: string } | null;
};
export type StandardVersion = { id: string; label?: string };
export type Standard = { id: string; code: string; versions: StandardVersion[] };
export type StandardDetail = { catalog: CatalogRule[]; disabled_rule_codes: string[] };

export type CustomRule = {
  id: string;
  name: string;
  category?: string;
  kind: string;
  severity: string;
  pattern?: string;
  replacement?: string;
  target_zone?: string;
  message?: string;
  enabled: boolean;
  validated: boolean;
};

export type ImportMode = "replace" | "add" | "update" | "overwrite";
export type RuleImportResultDto = {
  mode: ImportMode;
  imported: number;
  created: number;
  updated: number;
  replaced_count: number;
  by_kind: Record<string, number>;
  skipped: string[];
  llm_used: boolean;
};

export const standardsApi = {
  list: () => api<Standard[]>("/standards"),
  detail: (sid: string, vid: string) =>
    api<StandardDetail>(`/standards/${sid}/versions/${vid}`),
  reset: (sid: string, vid: string) =>
    api<unknown>(`/standards/${sid}/versions/${vid}/reset`, { method: "POST" }),
  toggle: (sid: string, vid: string, code: string, enabled: boolean) =>
    api<unknown>(`/standards/${sid}/versions/${vid}/rules/toggle`, {
      method: "POST",
      body: JSON.stringify({ code, enabled }),
    }),
  saveRule: (sid: string, vid: string, code: string, body: Record<string, unknown>) =>
    api<unknown>(`/standards/${sid}/versions/${vid}/rules/${encodeURIComponent(code)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRule: (sid: string, vid: string, code: string) =>
    api<unknown>(`/standards/${sid}/versions/${vid}/rules/${encodeURIComponent(code)}`, {
      method: "DELETE",
    }),
  addRule: (sid: string, vid: string, body: Record<string, unknown>) =>
    api<unknown>(`/standards/${sid}/versions/${vid}/rules`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export const rulesApi = {
  templateUrl: () => `${API_BASE}/rules/template`,
  list: () => api<CustomRule[]>("/rules"),
  create: (body: Record<string, unknown>) =>
    api<CustomRule>("/rules", { method: "POST", body: JSON.stringify(body) }),
  patch: (id: string, body: Record<string, unknown>) =>
    api<CustomRule>(`/rules/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/rules/${id}`, { method: "DELETE" }),
  validateAll: () => api<unknown>("/rules/validate-all", { method: "POST" }),
  inspect: async (file: File): Promise<{ sheets: { name: string; rows: string[][]; header_row: number }[] }> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/rules/inspect`, { method: "POST", body: fd });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as { sheets: { name: string; rows: string[][]; header_row: number }[] };
  },
  importChecklist: async (
    file: File,
    opts: {
      sheet?: string;
      header_row: number;
      topic_col?: string;
      check_col?: string;
      context_cols: number[];
      mode: ImportMode;
    },
  ): Promise<RuleImportResultDto> => {
    const fd = new FormData();
    fd.append("file", file);
    if (opts.sheet) fd.append("sheet", opts.sheet);
    fd.append("header_row", String(opts.header_row));
    if (opts.topic_col != null && opts.topic_col !== "") fd.append("topic_col", opts.topic_col);
    if (opts.check_col != null) fd.append("check_col", opts.check_col);
    fd.append("context_cols", JSON.stringify(opts.context_cols));
    fd.append("mode", opts.mode);
    const res = await fetch(`${API_BASE}/rules/import`, { method: "POST", body: fd });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as RuleImportResultDto;
  },
};
