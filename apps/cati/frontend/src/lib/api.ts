/**
 * Client API typé pour CATI (documents + items + export + settings + admin).
 */

const API_BASE = "/api/v1";

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

// ----- DTOs -----------------------------------------------------------------

export type HealthDto = {
  status: string;
  version: string;
  db: string;
  llm: "ok" | "untested" | "not_configured" | "disabled";
};

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  llm_enabled: boolean;
  llm_tested: boolean;
};

export type TestConnectionDto = { ok: boolean; models: string[]; error: string | null };

export type AdminStatsDto = { documents: number; items: number; total_size_bytes: number };

export type HeaderMeta = {
  module: string;
  otan_supplier: string;
  drw: string;
  top_assembly: string;
  bom_title: string;
};

export type ChallengeIssue = { field: string; deterministic: string; llm: string };
export type ChallengeVerdict = "ok" | "warning" | "missing" | "extra";
export type ChallengeRow = {
  fig: string;
  verdict: ChallengeVerdict;
  issues: ChallengeIssue[];
  llm_only?: Record<string, string> | null;
};
export type ChallengeSummary = {
  ok: number;
  warning: number;
  missing: number;
  extra: number;
  total: number;
  clean: boolean;
};
export type ChallengeReport = {
  status: "none" | "done" | "skipped";
  reason?: string | null;
  method?: string | null;
  summary: ChallengeSummary;
  rows: ChallengeRow[];
};

export type DocumentDto = {
  id: string;
  filename: string;
  size: number;
  page_count: number;
  status: string;
  extraction_method: string;
  item_count: number;
  header_meta: HeaderMeta;
  warnings: string[];
  challenge: ChallengeReport;
  error: string | null;
  created_at: string;
};

export type UploadItemResult = {
  filename: string;
  document_id: string | null;
  status: "created" | "duplicate" | "error";
  item_count: number;
  error: string | null;
};

export type ItemFields = Record<string, string | number | null>;

export type ItemDto = {
  id: string;
  order_index: number;
  source_page: number | null;
  fields: ItemFields;
  included: boolean;
  edited: boolean;
};

export type ItemsDto = {
  document_id: string;
  method: string;
  warnings: string[];
  items: ItemDto[];
};

// ----- clients --------------------------------------------------------------

export const healthApi = {
  read: () => api<HealthDto>("/health"),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  save: (body: Partial<Record<keyof SettingsDto | "api_key", unknown>>) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  resetAll: () => api<{ scope: string; deleted: Record<string, number> }>("/admin/reset/all", { method: "POST" }),
  resetDocuments: () =>
    api<{ scope: string; deleted: Record<string, number> }>("/admin/reset/documents", { method: "POST" }),
};

export const documentsApi = {
  list: () => api<DocumentDto[]>("/documents"),
  get: (id: string) => api<DocumentDto>(`/documents/${id}`),
  remove: (id: string) => api<DocumentDto>(`/documents/${id}`, { method: "DELETE" }),
  items: (id: string) => api<ItemsDto>(`/documents/${id}/items`),
  reextract: (id: string) => api<ItemsDto>(`/documents/${id}/extract?refresh=true`, { method: "POST" }),
  challenge: (id: string) => api<ChallengeReport>(`/documents/${id}/challenge`, { method: "POST" }),
  getChallenge: (id: string) => api<ChallengeReport>(`/documents/${id}/challenge`),
  saveHeaderMeta: (id: string, meta: HeaderMeta) =>
    api<DocumentDto>(`/documents/${id}/header-meta`, { method: "PUT", body: JSON.stringify(meta) }),
  upload: async (files: File[]): Promise<{ results: UploadItemResult[] }> => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const response = await fetch(`${API_BASE}/documents`, { method: "POST", body: form });
    if (!response.ok) {
      const error = (await response.json().catch(() => null)) as ApiError | null;
      throw error ?? { code: "UPLOAD_FAILED", message: response.statusText, detail: null, request_id: "" };
    }
    return (await response.json()) as { results: UploadItemResult[] };
  },
};

export const itemsApi = {
  patch: (docId: string, itemId: string, body: { fields?: ItemFields; included?: boolean }) =>
    api<ItemDto>(`/documents/${docId}/items/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  create: (docId: string, fields: ItemFields, afterId?: string) =>
    api<ItemDto>(`/documents/${docId}/items`, {
      method: "POST",
      body: JSON.stringify({ fields, after_id: afterId ?? null }),
    }),
  remove: (docId: string, itemId: string) =>
    api<ItemsDto>(`/documents/${docId}/items/${itemId}`, { method: "DELETE" }),
  reorder: (docId: string, orderedIds: string[]) =>
    api<ItemsDto>(`/documents/${docId}/items/reorder`, {
      method: "POST",
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),
};

/** Télécharge le .xlsx généré (blob -> lien <a download>). */
export async function downloadExport(docId: string, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE}/documents/${docId}/export.xlsx`);
  if (!response.ok) {
    throw { code: "EXPORT_FAILED", message: response.statusText, detail: null, request_id: "" } as ApiError;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
