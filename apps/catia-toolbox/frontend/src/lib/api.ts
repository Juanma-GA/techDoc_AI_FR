/**
 * Typed API client pour catia-toolbox. Reprend l'enveloppe d'erreur
 * unifiee du backend `{code, message, detail, request_id}`.
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
  const isForm = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: "application/json",
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    ...init,
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Types DTO
// ---------------------------------------------------------------------------

export type ImportDto = {
  id: string;
  source_mode: string;
  root_label: string;
  source_ref: string;
  node_count: number;
  created_at: string;
  metrics: TreeMetrics;
};

export type TreeMetrics = {
  node_count?: number;
  file_count?: number;
  folder_count?: number;
  max_depth?: number;
  avg_depth?: number;
  max_fanout?: number;
  duplicate_basenames_count?: number;
  deep_nesting_count?: number;
  naming?: { styles?: Record<string, number>; inconsistent?: boolean };
  [k: string]: unknown;
};

/** Renommage en masse SMGXML (etape 4) : entree + rapport par piece remplacee. */
export type SmgxmlBatchRenameInput = {
  scope?: BrowseScope;
  composer_root: string;
  converted_root: string;
  nomenclature_run_id: string;
  apply?: boolean;
};

export type SmgxmlBatchItemDto = {
  sin: string;
  old_pn: string;
  new_pn: string;
  old_stem: string;
  new_stem: string;
  assembly: string;
  replacements: number;
  archived: string[];
  copied: string[];
  status: string;
  message: string;
  applied: boolean;
};

export type SmgxmlBatchDto = {
  items: SmgxmlBatchItemDto[];
  summary: Record<string, number>;
};

export type SettingsDto = {
  api_key_set: boolean;
  base_url: string;
  chat_model: string;
  embed_model: string;
  llm_enabled: boolean;
  llm_tested?: boolean;
  onedrive_input_root: string;
  onedrive_output_root: string;
  composer_license_server: string;
  composer_converter_path: string;
  composer_settings_path: string;
};

export type SettingsInput = {
  api_key?: string;
  base_url?: string;
  chat_model?: string;
  embed_model?: string;
  llm_enabled?: boolean;
  onedrive_input_root?: string;
  onedrive_output_root?: string;
  composer_license_server?: string;
  composer_converter_path?: string;
  composer_settings_path?: string;
};

export type BrowseScope = "input" | "output";

export type BrowseRootsDto = {
  input: string;
  output: string;
  detected: string[];
};

export type BrowseEntryDto = {
  name: string;
  path: string;
  kind: "file" | "folder";
  ext: string;
  size: number;
  mtime: string | null;
  rel?: string;
};

export type BrowseListDto = {
  scope: BrowseScope;
  root: string;
  path: string;
  entries: BrowseEntryDto[];
};

export type LocalUploadFileDto = { path: string; rel: string; size: number };
export type LocalUploadDto = { root: string; files: LocalUploadFileDto[] };

export type BrowsePreviewDto = {
  sheets: string[];
  sheet: string;
  rows: string[][];
};

export type TestConnectionDto = { ok: boolean; models: string[]; error?: string | null };

export type AdminStatsDto = {
  imports: number;
  nodes: number;
  runs: number;
  suggestions: number;
  diffs: number;
  checks: number;
  conversions: number;
  replacements: number;
  colorizations: number;
  nomenclatures: number;
  smgxml_runs: number;
  qc_checklists: number;
  total_size_bytes: number;
};

export type DiffRunDto = {
  id: string;
  base_import_id: string;
  other_import_id: string;
  status: string;
  summary: Record<string, number>;
  created_at: string;
};
export type DiffEntryDto = { id: string; rel_path: string; change_type: string; detail: string };

export type CheckRunDto = {
  id: string;
  import_id: string;
  status: string;
  summary: Record<string, number>;
  created_at: string;
};
export type CheckResultDto = { id: string; rule: string; severity: string; rel_path: string; message: string };
export type CheckInput = {
  rules?: string[];
  max_depth?: number;
  naming_style?: string;
  forbidden_extensions?: string[];
};

export type ConversionRunDto = {
  id: string;
  import_id: string;
  status: string;
  summary: Record<string, number | string>;
  created_at: string;
};
export type ConversionItemDto = {
  id: string;
  source_path: string;
  target_path: string;
  source_ext: string;
  status: string;
};
export type ConversionExecDto = {
  dry_run: boolean;
  returncode: number;
  stdout: string;
  stderr: string;
  base: string;
  converted: number;
  failed: number;
};

export type ComposerConverterStatusDto = {
  available: boolean;
  executable: string;
  settings_file: string;
  version: string;
  message: string;
};

export type ReplacementRunDto = {
  id: string;
  import_id: string;
  status: string;
  summary: Record<string, number>;
  created_at: string;
};
export type ReplacementItemDto = {
  id: string;
  occurrence_path: string;
  old_ref: string;
  new_ref: string;
  status: string;
};

// ----- Health --------------------------------------------------------------

export type LlmState = "ok" | "untested" | "not_configured" | "disabled";

export type HealthDto = {
  status: string;
  version: string;
  db: string;
  llm: LlmState;
};

// ----- Etape 1 : Identification (nomenclature .xlsm + DE .zip) --------------

export type NomenclatureRunDto = {
  id: string;
  source_ref: string;
  sheet: string;
  status: string;
  summary: Record<string, number | string[] | string>;
  created_at: string;
};

export type NomenclatureItemDto = {
  id: string;
  catpart: string;
  designation: string;
  sin: string;
  version: string;
  to_treat: boolean;
  to_treat_value: string;
  optimized: boolean;
  replaced: boolean;
  old_pn: string;
  new_pn: string;
  old_rev: string;
  new_rev: string;
  color_ref: string;
  materials: string;
  mono_body: boolean;
  mono_color: boolean;
  color_r: number;
  color_g: number;
  color_b: number;
  source_row: number;
};

export type NomenclaturePreviewDto = {
  sheets: string[];
  sheet: string;
  header_row_detected: number;
  columns_detected: string[];
  columns_map: Record<string, number>;
  rows: string[][];
};

export type NomenclatureMapping = {
  header_row: number;
  catpart?: number;
  designation?: number;
  sin?: number;
  version?: number;
  to_treat?: number;
  optimized?: number;
  color?: number;
  old_pn?: number;
  new_pn?: number;
  old_rev?: number;
  new_rev?: number;
  replaced?: number;
  color_ref?: number;
  materials?: number;
};

// Etape Mono-Corps : onglet Materiaux (identite seule ; tous les slots compares).
export type MonoCorpsInput = {
  scope?: BrowseScope;
  path: string;
  sheet?: string;
  header_row: number;
  identity_field: string;
  identity_col: number;
  // Optionnel : colonnes slots explicites. Prioritaire sur first_slot_col.
  slot_cols?: number[];
  // 1re colonne Slot (0-based) : comparee a toutes les colonnes suivantes.
  first_slot_col?: number;
  // Optionnel : run de nomenclature auquel appliquer mono_body.
  run_id?: string;
};

export type MonoCorpsItemDto = { identity: string; old_pn: string; slots: string[]; mono_body: boolean };
export type MonoCorpsResultDto = {
  items: MonoCorpsItemDto[];
  summary: Record<string, number | boolean | number[]>;
};

export type ZipEntryDto = { name: string; size: number; is_dir: boolean };

export type ZipListDto = { path: string; count: number; entries: ZipEntryDto[] };

// Import unifie depuis un .zip : l'import cree + l'apercu du contenu.
export type ZipImportDto = ImportDto & { count: number; entries: ZipEntryDto[] };

// Comparaison de deux nomenclatures (versions V0 vs V1) par SIN.
export type SinEntryDto = { sin: string; old_pn: string; old_pn_v2: string; designation: string };
export type PnChangeDto = { sin: string; old_pn: string; old_pn_v2: string; designation: string };
export type NomenclatureCompareDto = {
  base_run_id: string;
  other_run_id: string;
  added_sin: SinEntryDto[];
  removed_sin: SinEntryDto[];
  changed_pn: PnChangeDto[];
  summary: Record<string, number>;
};
export type NomenclatureCompareMode = "chronology" | "reference";
export type NomenclatureMatrixState = "unchanged" | "added" | "removed" | "changed" | "reference";
export type NomenclatureMatrixRowDto = {
  sin: string;
  designation: string;
  cells: Array<{
    run_id: string;
    present: boolean;
    pn: string;
    state: NomenclatureMatrixState;
  }>;
};
export type NomenclatureMultiCompareDto = {
  mode: NomenclatureCompareMode;
  run_ids: string[];
  reference_run_id: string | null;
  comparisons: NomenclatureCompareDto[];
  matrix: NomenclatureMatrixRowDto[];
  summary: Record<string, number>;
};

// ----- Etapes 3 & 4 : SMGXML -----------------------------------------------

export type SmgxmlRunDto = {
  id: string;
  source_ref: string;
  operation: string;
  status: string;
  applied: boolean;
  backup_path: string;
  output_path: string;
  summary: Record<string, number>;
  created_at: string;
};

export type SmgxmlChangeDto = {
  id: string;
  target: string;
  change_type: string;
  old_value: string;
  new_value: string;
};

export type RenamePair = { old: string; new: string };

export type SmgxmlRenameInput = {
  scope?: BrowseScope;
  path: string;
  mapping: RenamePair[];
  apply?: boolean;
};

// ----- Etape 5 : Controle Qualite (checklist) ------------------------------

export type QcItemDto = {
  id: string;
  label: string;
  category: string;
  status: "pending" | "ok" | "ko" | "na";
  comment: string;
  position: number;
};

export type QcSummaryDto = {
  pending: number;
  ok: number;
  ko: number;
  na: number;
  done: number;
  total: number;
};

export type QcChecklistDto = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  items: QcItemDto[];
  summary: QcSummaryDto;
};

export type QcChecklistCreateInput = {
  title?: string;
  template?: string | null;
  items?: { label: string; category?: string }[];
};

export type QcItemUpdateInput = { status?: string; comment?: string };

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const importsApi = {
  list: () => request<ImportDto[]>("/imports"),
  get: (id: string) => request<ImportDto>(`/imports/${id}`),
  scan: (path: string, maxNodes?: number) =>
    request<ImportDto>("/imports/scan", {
      method: "POST",
      body: JSON.stringify({ path, ...(maxNodes ? { max_nodes: maxNodes } : {}) }),
    }),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ImportDto>("/imports/upload", { method: "POST", body: fd });
  },
  select: (paths: string[], scope: BrowseScope = "input") =>
    request<ImportDto>("/imports/select", {
      method: "POST",
      body: JSON.stringify({ scope, paths }),
    }),
  /** Import unifie d'un .zip : cree l'import ET renvoie le listing du contenu. */
  zip: (path: string, scope: BrowseScope = "input") =>
    request<ZipImportDto>("/imports/zip", {
      method: "POST",
      body: JSON.stringify({ scope, path }),
    }),
  remove: (id: string) => request<void>(`/imports/${id}`, { method: "DELETE" }),
};

export const browseApi = {
  roots: () => request<BrowseRootsDto>("/browse/roots"),
  uploadLocal: (files: File[]) => {
    const fd = new FormData();
    files.forEach((file) => fd.append("files", file, file.webkitRelativePath || file.name));
    return request<LocalUploadDto>("/browse/local-upload", { method: "POST", body: fd });
  },
  list: (path: string, scope: BrowseScope = "input") =>
    request<BrowseListDto>("/browse/list", {
      method: "POST",
      body: JSON.stringify({ scope, path }),
    }),
  /** Liste a plat tous les fichiers (recursif) sous un dossier. */
  files: (path: string, scope: BrowseScope = "input") =>
    request<BrowseListDto>("/browse/files", {
      method: "POST",
      body: JSON.stringify({ scope, path }),
    }),
  /** Apercu generique d'un classeur Excel : onglets + premieres lignes. */
  preview: (body: { scope?: BrowseScope; path: string; sheet?: string; rows?: number }) =>
    request<BrowsePreviewDto>("/browse/preview", {
      method: "POST",
      body: JSON.stringify({ scope: "input", ...body }),
    }),
};

export const settingsApi = {
  read: () => request<SettingsDto>("/settings"),
  write: (payload: SettingsInput) =>
    request<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(payload) }),
  test: () => request<TestConnectionDto>("/settings/test", { method: "POST" }),
};

export const diffApi = {
  create: (baseImportId: string, otherImportId: string) =>
    request<DiffRunDto>("/diff", {
      method: "POST",
      body: JSON.stringify({ base_import_id: baseImportId, other_import_id: otherImportId }),
    }),
  entries: (runId: string, changeType?: string) =>
    request<DiffEntryDto[]>(`/diff/${runId}/entries${changeType ? `?change_type=${changeType}` : ""}`),
};

export const checksApi = {
  rules: () => request<string[]>("/checks/rules"),
  run: (importId: string, config: CheckInput) =>
    request<CheckRunDto>(`/imports/${importId}/check`, { method: "POST", body: JSON.stringify(config) }),
  results: (runId: string) => request<CheckResultDto[]>(`/checks/${runId}/results`),
};

export const conversionApi = {
  status: () => request<ComposerConverterStatusDto>("/conversion/composer-status"),
  run: (importId: string, config?: { target_dir?: string; target_ext?: string }) =>
    request<ConversionRunDto>(`/imports/${importId}/conversion`, {
      method: "POST",
      body: JSON.stringify(config ?? {}),
    }),
  items: (runId: string) => request<ConversionItemDto[]>(`/conversions/${runId}/items`),
  /** Selection / deselection manuelle d'un fichier a convertir. */
  setItem: (runId: string, itemId: string, status: "accepted" | "rejected" | "pending") =>
    request<ConversionItemDto>(`/conversions/${runId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  bulkStatus: (runId: string, itemIds: string[], status: "accepted" | "rejected" | "pending") =>
    request<ConversionItemDto[]>(`/conversions/${runId}/items/bulk-status`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds, status }),
    }),
  /** Execute le script en local (dry_run par defaut ; reel exige confirm). */
  execute: (runId: string, dryRun: boolean, confirm = false) =>
    request<ConversionExecDto>(`/conversions/${runId}/execute`, {
      method: "POST",
      body: JSON.stringify({ dry_run: dryRun, confirm }),
    }),
};

export const replacementApi = {
  run: (importId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ReplacementRunDto>(`/imports/${importId}/replacement`, { method: "POST", body: fd });
  },
  /** Mapping depuis un fichier de la Source (scope input) — preview /replacement/source. */
  source: (importId: string, path: string, scope: BrowseScope = "input") =>
    request<ReplacementRunDto>(`/imports/${importId}/replacement/source`, {
      method: "POST",
      body: JSON.stringify({ scope, path }),
    }),
  items: (runId: string) => request<ReplacementItemDto[]>(`/replacements/${runId}/items`),
};

export const adminApi = {
  stats: () => request<AdminStatsDto>("/admin/stats"),
  reset: (scope: string) =>
    request<{ scope: string; deleted: Record<string, number> }>(`/admin/reset/${scope}`, {
      method: "POST",
    }),
  resetAll: () =>
    request<{ scope: string; deleted: Record<string, number> }>("/admin/reset/all", {
      method: "POST",
    }),
};

export const healthApi = {
  get: () => request<HealthDto>("/health"),
};

export const identificationApi = {
  list: () => request<NomenclatureRunDto[]>("/identification"),
  get: (id: string) => request<NomenclatureRunDto>(`/identification/${id}`),
  preview: (body: { scope?: BrowseScope; path: string; sheet?: string; rows?: number }) =>
    request<NomenclaturePreviewDto>("/identification/preview", {
      method: "POST",
      body: JSON.stringify({ scope: "input", ...body }),
    }),
  nomenclature: (body: {
    scope?: BrowseScope;
    path: string;
    sheet?: string;
    mapping?: NomenclatureMapping;
  }) =>
    request<NomenclatureRunDto>("/identification/nomenclature", {
      method: "POST",
      body: JSON.stringify({ scope: "input", ...body }),
    }),
  items: (
    id: string,
    filters?: {
      toTreat?: boolean;
      optimized?: boolean;
      monoColor?: boolean;
      monoBody?: boolean;
      replaced?: boolean;
      hasColor?: boolean;
    },
  ) => {
    const qs = new URLSearchParams();
    if (filters?.toTreat !== undefined) qs.set("to_treat", String(filters.toTreat));
    if (filters?.optimized !== undefined) qs.set("optimized", String(filters.optimized));
    if (filters?.monoColor !== undefined) qs.set("mono_color", String(filters.monoColor));
    if (filters?.monoBody !== undefined) qs.set("mono_body", String(filters.monoBody));
    if (filters?.replaced !== undefined) qs.set("replaced", String(filters.replaced));
    if (filters?.hasColor !== undefined) qs.set("has_color", String(filters.hasColor));
    const s = qs.toString();
    return request<NomenclatureItemDto[]>(`/identification/${id}/items${s ? `?${s}` : ""}`);
  },
  /** Comparaison de deux nomenclatures (versions A vs B) par SIN. */
  compare: (baseRunId: string, otherRunId: string) =>
    request<NomenclatureCompareDto>("/identification/compare", {
      method: "POST",
      body: JSON.stringify({ base_run_id: baseRunId, other_run_id: otherRunId }),
    }),
  compareMulti: (runIds: string[], mode: NomenclatureCompareMode, referenceRunId?: string) =>
    request<NomenclatureMultiCompareDto>("/identification/compare/multi", {
      method: "POST",
      body: JSON.stringify({
        run_ids: runIds,
        mode,
        reference_run_id: mode === "reference" ? referenceRunId : undefined,
      }),
    }),
  /** Etape Mono-Corps : onglet Materiaux (identite + n colonnes slots).
   * Analyse autonome ; applique mono_body au run si `run_id` est fourni. */
  monoCorps: (body: MonoCorpsInput) =>
    request<MonoCorpsResultDto>("/identification/mono-corps", {
      method: "POST",
      body: JSON.stringify({ scope: "input", ...body }),
    }),
  remove: (id: string) => request<void>(`/identification/${id}`, { method: "DELETE" }),
};

export const smgxmlApi = {
  list: () => request<SmgxmlRunDto[]>("/smgxml"),
  get: (id: string) => request<SmgxmlRunDto>(`/smgxml/${id}`),
  rename: (body: SmgxmlRenameInput) =>
    request<SmgxmlRunDto>("/smgxml/rename", {
      method: "POST",
      body: JSON.stringify({ scope: "input", apply: false, ...body }),
    }),
  changes: (id: string) => request<SmgxmlChangeDto[]>(`/smgxml/${id}/changes`),
  /** Renommage en masse (etape 4) des pieces remplacees d'une nomenclature. */
  batchRename: (body: SmgxmlBatchRenameInput) =>
    request<SmgxmlBatchDto>("/smgxml/batch-rename", {
      method: "POST",
      body: JSON.stringify({ scope: "input", apply: false, ...body }),
    }),
};

export const qcApi = {
  list: () => request<QcChecklistDto[]>("/qc/checklists"),
  get: (id: string) => request<QcChecklistDto>(`/qc/checklists/${id}`),
  create: (body: QcChecklistCreateInput) =>
    request<QcChecklistDto>("/qc/checklists", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: string) => request<void>(`/qc/checklists/${id}`, { method: "DELETE" }),
  setItem: (id: string, patch: QcItemUpdateInput) =>
    request<QcItemDto>(`/qc/items/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
};

/** URL de telechargement direct (CSV / script) — consommee via <a href>. */
export const exportUrl = {
  diffCsv: (runId: string) => `${API_BASE}/diff/${runId}/export.csv`,
  checksCsv: (runId: string) => `${API_BASE}/checks/${runId}/export.csv`,
  conversionCsv: (runId: string) => `${API_BASE}/conversions/${runId}/export.csv`,
  conversionScript: (runId: string) => `${API_BASE}/conversions/${runId}/export.script`,
  replacementCsv: (runId: string) => `${API_BASE}/replacements/${runId}/export.csv`,
  replacementMacro: (runId: string) => `${API_BASE}/replacements/${runId}/export.macro`,
  identificationCsv: (
    runId: string,
    filters?: { toTreat?: boolean; optimized?: boolean; replaced?: boolean; monoBody?: boolean },
  ) => {
    const qs = new URLSearchParams();
    if (filters?.toTreat !== undefined) qs.set("to_treat", String(filters.toTreat));
    if (filters?.optimized !== undefined) qs.set("optimized", String(filters.optimized));
    if (filters?.replaced !== undefined) qs.set("replaced", String(filters.replaced));
    if (filters?.monoBody !== undefined) qs.set("mono_body", String(filters.monoBody));
    const s = qs.toString();
    return `${API_BASE}/identification/${runId}/export.csv${s ? `?${s}` : ""}`;
  },
  nomenclatureCompareCsv: (baseRunId: string, otherRunId: string) =>
    `${API_BASE}/identification/compare/export.csv?base_run_id=${baseRunId}&other_run_id=${otherRunId}`,
  qcCsv: (checklistId: string) => `${API_BASE}/qc/checklists/${checklistId}/export.csv`,
};

// Keep the frontend client aligned with the routes registered by the backend.

