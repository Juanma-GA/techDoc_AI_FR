/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

import type { DmValidationResult, WizardState } from "./wizardTypes";
export type {
  Candidate,
  DmPreview,
  DmValidationResult,
  DmValidationStatus,
  DmValidationViolation,
  DmrlMatchRank,
  DmrlRow,
  DmrlTypeIssue,
  NodeRef,
  Override,
  PreviewSnippet,
  TreeNode,
  WizardDm,
  WizardResources,
  WizardState,
  WizardStep,
} from "./wizardTypes";

// Surchargeable au build (VITE_API_BASE_URL) pour un deploiement en sous-chemin
// IIS (ex. /app/s1000d-extractor/api/v1). Defaut relatif '/api/v1' en local.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

// Store X-Request-Id for tracing end-to-end (backend → frontend → logs)
let _currentRequestId: string | null = null;

export function getRequestId(): string | null {
  return _currentRequestId;
}

export type ApiError = {
  code: string;
  message: string;
  detail: unknown;
  request_id: string;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  // Include X-Request-Id in outgoing request (if we have one from a previous response)
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (_currentRequestId) {
    headers["X-Request-Id"] = _currentRequestId;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers: { ...headers, ...(init?.headers ?? {}) },
    ...init,
  });

  // Extract and store X-Request-Id from response for tracing
  const responseRequestId = response.headers.get("X-Request-Id");
  if (responseRequestId) {
    _currentRequestId = responseRequestId;
  }

  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw new Error(error?.message || response.statusText || "Erreur");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ----- Standard DTOs --------------------------------------------------------

export type LlmStatus = "ok" | "disabled" | "not_configured" | "untested";
export type HealthDto = { status: string; version: string; llm: LlmStatus | string };

export type AdminStatsDto = {
  documents: number;
  extracted: number;
  brex_profiles: number;
  total_size_bytes: number;
};
export type AdminResetDto = { deleted: Record<string, number> };

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  llm_enabled: boolean;
  demo_enabled: boolean;
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  reset: (scope: "documents" | "all", confirmToken: string) =>
    api<AdminResetDto>(
      `/admin/reset/${scope}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "POST" },
    ),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
    llm_enabled?: boolean;
    demo_enabled?: boolean;
  }) => api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

// ----- Domain types ---------------------------------------------------------

export type S1000dIssue = "4.1" | "4.2";
export type ContextHint = "mixed" | "descriptive" | "procedural";

export type BrexProfile = {
  id: string;
  name: string;
  s1000d_issue: string;
};

export type BrexObjectValue = {
  value_allowed: string | null;
  value_text: string;
  value_form: string | null;
  value_tailoring: string;
};

export type BrexRule = {
  rule_id: string | null;
  object_path: string;
  allowed_flag: string;
  object_use: string;
  object_values: BrexObjectValue[];
  rules_context: string | null;
  context_id: string | null;
  severity_level: string | null;
  supported: boolean;
  support_status: "automatic" | "contextual" | "unsupported";
  support_reason: string | null;
};

export type UnsupportedBrexRule = {
  rule_type: string;
  rule_id: string | null;
  description: string;
};

export type BrexProfileDetail = BrexProfile & {
  dmc: string;
  dm_code: Record<string, string>;
  rules: BrexRule[];
  unsupported_rules: UnsupportedBrexRule[];
};

export type DocumentOut = {
  id: string;
  filename: string;
  source_format: string;
  status: string;
};

export type PdfCutCandidate = {
  page: number;
  score: number;
  reasons: string[];
  preview: string;
};

export type PdfCutDetection = {
  validation_required: boolean;
  selected_page: number | null;
  selected_end_page: number | null;
  default_start_page: number;
  total_pages: number;
  dmrl_titles: string[];
  candidates: PdfCutCandidate[];
};

export type DmVersion = {
  id: string;
  doc_id: string;
  dm_code: string;
  author: string;
  status: string;
  notes?: string | null;
  created_at: string;
  content_length: number;
};

export type DmVersionContent = Omit<DmVersion, "content_length"> & { content: string };

export const versioningApi = {
  list: (docId: string, dmCode?: string) =>
    api<DmVersion[]>(`/documents/${docId}/dm-versions${dmCode ? `?dm_code=${encodeURIComponent(dmCode)}` : ""}`),
  get: (docId: string, versionId: string) =>
    api<DmVersionContent>(`/documents/${docId}/dm-versions/${versionId}`),
  restore: (docId: string, versionId: string) =>
    api<{ restored_version_id: string }>(`/documents/${docId}/dm-versions/${versionId}/restore`, {
      method: "POST",
    }),
};

export const brexApi = {
  list: () => api<BrexProfile[]>("/brex"),
  detail: (brexId: string) => api<BrexProfileDetail>(`/brex/${encodeURIComponent(brexId)}`),
  delete: (brexId: string, confirmToken: string) =>
    api<{ id: string; status: string }>(
      `/brex/${encodeURIComponent(brexId)}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "DELETE" },
    ),
  upload: async (
    file: File,
    name: string,
    issue: S1000dIssue,
  ): Promise<BrexProfile> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    fd.append("s1000d_issue", issue);
    const res = await fetch(`${API_BASE}/brex`, { method: "POST", body: fd });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as BrexProfile;
  },
};

export const documentsApi = {
  list: () => api<DocumentOut[]>("/documents"),
  get: (docId: string) => api<DocumentOut>(`/documents/${docId}`),
  delete: (docId: string, confirmToken: string) =>
    api<{ id: string; status: string }>(
      `/documents/${docId}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "DELETE" },
    ),
  upload: async (
    file: File,
    issue: S1000dIssue,
    hint: ContextHint,
    brexId?: string,
  ): Promise<DocumentOut> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("s1000d_issue", issue);
    fd.append("context_hint", hint);
    if (brexId) fd.append("brex_id", brexId);
    const res = await fetch(`${API_BASE}/documents`, { method: "POST", body: fd });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as DocumentOut;
  },
};

export const pdfCutApi = {
  detect: (docId: string, title?: string) =>
    api<PdfCutDetection>(`/documents/${docId}/pdf-cut/detect`, {
      method: "POST",
      body: JSON.stringify(title ? { title } : {}),
    }),
  confirm: (docId: string, startPage: number, endPage: number) =>
    api<{ page: number; start_page: number; end_page: number; page_count: number; status: string }>(
      `/documents/${docId}/pdf-cut/confirm`,
      { method: "POST", body: JSON.stringify({ start_page: startPage, end_page: endPage }) },
    ),
  previewUrl: (docId: string, page: number) =>
    `${API_BASE}/documents/${docId}/pdf-cut/preview/${page}`,
};

export type ResourceKind = "dmrl" | "cir" | "brex_rules" | "dm_header";
export type ResourceUploadDto = { kind: ResourceKind; count: number };
export type MigrationInputKind = "document" | ResourceKind;
export type MigrationInputMapping = {
  issue: S1000dIssue | "5.0";
  context_hint: ContextHint;
  brex_id: string | null;
  files: Partial<Record<MigrationInputKind, { filename: string }>>;
};

export const migrationInputsApi = {
  read: () => api<MigrationInputMapping>("/migration-inputs"),
  file: async (kind: MigrationInputKind, filename: string): Promise<File> => {
    const res = await fetch(`${API_BASE}/migration-inputs/${kind}`);
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    const blob = await res.blob();
    return new File([blob], filename, { type: blob.type });
  },
};

// Ressources client optionnelles : DMRL, CIR, regles BREX et template d'en-tete.
export const resourcesApi = {
  upload: async (docId: string, kind: ResourceKind, file: File): Promise<ResourceUploadDto> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/documents/${docId}/resources/${kind}`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      const e = (await res.json().catch(() => null)) as ApiError | null;
      throw new Error(e?.message || res.statusText);
    }
    return (await res.json()) as ResourceUploadDto;
  },
  pmcUrl: (docId: string) => `${API_BASE}/documents/${docId}/pmc`,
};

export const wizardApi = {
  get: (docId: string) => api<WizardState>(`/documents/${docId}/wizard`),
  // action : "update" | "advance" | "back" (+ params optionnels).
  action: (docId: string, action: string, params?: Record<string, unknown>) =>
    api<WizardState>(`/documents/${docId}/wizard/${action}`, {
      method: "POST",
      ...(params ? { body: JSON.stringify(params) } : {}),
    }),
  dmXmlUrl: (docId: string, dmId: string) =>
    `${API_BASE}/documents/${docId}/wizard/dm/${dmId}/xml`,
  downloadDmFile: async (docId: string, dmId: string): Promise<File> => {
    const response = await fetch(
      `${API_BASE}/documents/${encodeURIComponent(docId)}/wizard/dm/${encodeURIComponent(dmId)}/xml`,
    );
    if (!response.ok) {
      const error = (await response.json().catch(() => null)) as ApiError | null;
      throw new Error(error?.message || response.statusText || "Erreur");
    }
    const disposition = response.headers.get("Content-Disposition");
    const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? `${dmId}.xml`;
    return new File([await response.blob()], filename, { type: "application/xml" });
  },
  zipUrl: (
    docId: string,
    options: {
      maxDimension?: number;
      format?: "original" | "jpeg" | "png";
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (options.maxDimension !== undefined) {
      params.set("max_dimension", String(options.maxDimension));
    }
    if (options.format && options.format !== "original") {
      params.set("image_format", options.format);
    }
    const query = params.toString();
    return `${API_BASE}/documents/${docId}/wizard/zip${query ? `?${query}` : ""}`;
  },
  images: (docId: string) => api<string[]>(`/documents/${docId}/wizard/images`),
  imageUrl: (docId: string, name: string) =>
    `${API_BASE}/documents/${docId}/wizard/images/${encodeURIComponent(name)}`,
};

export const validationApi = {
  validate: async (
    files: File[],
    issueOverrides: Array<string | null> = [],
    filenames: string[] = [],
  ): Promise<{ results: DmValidationResult[] }> => {
    const form = new FormData();
    files.forEach((file, index) => {
      form.append("files", file, filenames[index] || file.webkitRelativePath || file.name);
    });
    form.append("issue_overrides", JSON.stringify(issueOverrides));

    const headers: Record<string, string> = {};
    if (_currentRequestId) headers["X-Request-Id"] = _currentRequestId;
    const response = await fetch(`${API_BASE}/validation/dms`, {
      method: "POST",
      headers,
      body: form,
    });
    const responseRequestId = response.headers.get("X-Request-Id");
    if (responseRequestId) _currentRequestId = responseRequestId;
    if (!response.ok) {
      const error = (await response.json().catch(() => null)) as
        | (ApiError & { detail?: string })
        | null;
      throw new Error(error?.message || error?.detail || response.statusText || "Erreur");
    }
    return (await response.json()) as { results: DmValidationResult[] };
  },
};

/**
 * Lance la generation et consomme le flux SSE (fetch +
 * ReadableStream ; EventSource ne sait pas POST). `onEvent(event, data)`.
 */
export async function startWizardStream(
  docId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}/wizard/start_stream`, {
    method: "POST",
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r/g, "");
    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(data) as Record<string, unknown>;
      } catch {
        /* ignore */
      }
      onEvent(event, parsed);
    }
  }
}

export async function generatePmcStream(
  docId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}/validate-and-generate-pmc`, { method: "POST" });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r/g, "");
    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        onEvent(event, JSON.parse(data) as Record<string, unknown>);
      } catch {
        onEvent(event, {});
      }
    }
  }
}
