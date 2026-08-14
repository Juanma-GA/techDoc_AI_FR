/**
 * Typed API client. Replace with a generated client from `pnpm openapi:gen:<poc>`
 * once the backend OpenAPI is stable.
 */

// Surchargeable au build (VITE_API_BASE_URL) pour un deploiement en sous-chemin
// IIS (ex. /app/s1000d-extractor/api/v1). Defaut relatif '/api/v1' en local.
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
};
export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export const healthApi = { read: () => api<HealthDto>("/health") };

export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  reset: (scope: "documents" | "all") =>
    api<AdminResetDto>(`/admin/reset/${scope}`, { method: "POST" }),
};

export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: {
    api_key?: string;
    base_url?: string;
    chat_model?: string;
    embed_model?: string;
    llm_enabled?: boolean;
  }) => api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
  test: () => api<TestConnectionDto>("/settings/test", { method: "POST" }),
};

// ----- Domain types ---------------------------------------------------------

export type S1000dIssue = "4.2" | "5.0";
export type ContextHint = "mixed" | "descriptive" | "procedural";

export type BrexProfile = {
  id: string;
  name: string;
  s1000d_issue: string;
};

export type Candidate = { element: string; score?: number; rationale?: string };

export type NodeRef = { kind: string; target?: string; target_kind?: string; text?: string };

export type TreeNode = {
  id: string;
  kind: string;
  text: string;
  context: string;
  confidence: number | null;
  candidates: Candidate[];
  children: TreeNode[];
  level?: number | null;
  page?: number | null;
  zone?: string;
  table_header?: string[] | null;
  icn?: string | null;
  refs?: NodeRef[] | null;
};

export type DocumentOut = {
  id: string;
  filename: string;
  source_format: string;
  status: string;
};

// ----- Wizard ---------------------------------------------------------------

export type WizardStep = "dmrl" | "split" | "type" | "structure" | "generate";

export type PreviewSnippet = {
  text: string;
  page: number | null;
  kind: string;
  zone?: string;
};

export type DmPreview = { head: PreviewSnippet[]; tail: PreviewSnippet[]; total: number };

export type WizardDm = {
  dm_id: string;
  title: string;
  dm_type: string;
  node_count: number;
  tree: TreeNode;
  violation_count: number;
  preview?: DmPreview;
  missing_fields?: string[];
  cir_unresolved?: string[];
};

export type WizardResources = {
  dmrl_count: number;
  has_cir: boolean;
  has_brex_rules: boolean;
};

export type DmrlRow = {
  index: number;
  arbo: string;
  dmc: string;
  title: string;
  dm_type: string;
  matched: boolean;
  page: number | null;
  matched_text: string;
};

export type WizardState = {
  step: WizardStep;
  split_level: string;
  steps?: WizardStep[];
  dms: WizardDm[];
  can_undo?: boolean;
  resources?: WizardResources;
  dmrl?: DmrlRow[];
};

export type Override = { dm_id: string; node_id: string; element: string };

export const brexApi = {
  list: () => api<BrexProfile[]>("/brex"),
};

export const documentsApi = {
  list: () => api<DocumentOut[]>("/documents"),
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

export type ResourceKind = "dmrl" | "cir" | "brex_rules";
export type ResourceUploadDto = { kind: ResourceKind; count: number };

// Ressources client optionnelles : DMRL (decoupage + PMC), CIR, regles BREX JSON.
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
  zipUrl: (docId: string) => `${API_BASE}/documents/${docId}/wizard/zip`,
  images: (docId: string) => api<string[]>(`/documents/${docId}/wizard/images`),
  imageUrl: (docId: string, name: string) =>
    `${API_BASE}/documents/${docId}/wizard/images/${encodeURIComponent(name)}`,
};

/**
 * Lance le demarrage de l'assistant et consomme le flux SSE (fetch +
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
