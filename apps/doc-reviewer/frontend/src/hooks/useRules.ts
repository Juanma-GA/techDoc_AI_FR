import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Rule } from "../types/domain";

export type RuleInput = {
  name: string;
  kind: Rule["kind"];
  pattern: string;
  replacement: string;
  severity: Rule["severity"];
  message: string;
  enabled: boolean;
  standard_version_id?: string | null;
};

export type RuleSuggestion = {
  name: string;
  kind: Rule["kind"];
  pattern: string;
  replacement: string;
  severity: Rule["severity"];
  message: string;
};

export type RuleSuggestResponse = {
  suggestions: RuleSuggestion[];
  documents_analyzed: number;
};

export function useRules(filter?: {
  standardVersionId?: string | null;
  includeTransverse?: boolean;
}) {
  const sv = filter?.standardVersionId ?? null;
  const includeTrans = filter?.includeTransverse ?? true;
  return useQuery({
    queryKey: ["rules", sv, includeTrans],
    queryFn: () => {
      if (!sv) return api.get<Rule[]>("/rules");
      const params = new URLSearchParams({
        standard_version_id: sv,
        include_transverse: String(includeTrans),
      });
      return api.get<Rule[]>(`/rules?${params.toString()}`);
    },
  });
}

export function useCreateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RuleInput) => api.post<Rule>("/rules", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function usePatchRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Partial<RuleInput>) =>
      api.patch<Rule>(`/rules/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
}

export function useSuggestRules() {
  return useMutation({
    mutationFn: () => api.post<RuleSuggestResponse>("/rules/suggest", {}),
  });
}

/** Suggestion de regles a partir de documents CONFORMES uploades directement
 *  (PDF / Word) — pour se baser sur du bon contenu. */
export function useSuggestRulesFromFiles() {
  return useMutation({
    mutationFn: (files: File[]) => {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      return api.upload<RuleSuggestResponse>("/rules/suggest/from-files", fd);
    },
  });
}

export type ChecklistImportResult = {
  mode: string;
  imported: number;
  replaced_count: number;
  by_kind: Record<string, number>;
  skipped_manual: number;
  skipped: string[];
  rules: CompiledRuleSummary[];
};

export type CompiledRuleSummary = {
  id: string;
  topic: string;
  severity: "info" | "warning" | "error";
  execution: "deterministic" | "semantic" | "manual" | "unsupported";
  active: boolean;
  source: "standard_rule" | "user_checklist";
  origin_ref: string | null;
  semantic_instruction: string | null;
  manual_instruction: string | null;
  compilation_error: string | null;
  detail: string | null;
};

export function useCompiledRules(standardVersionIds: string[] = []) {
  const selectedIds = [...standardVersionIds].sort();
  return useQuery({
    queryKey: ["compiled-rules", selectedIds],
    queryFn: () => {
      const params = new URLSearchParams();
      selectedIds.forEach((id) => params.append("standard_version_id", id));
      const query = params.toString();
      return api.get<CompiledRuleSummary[]>(`/compiled-rules${query ? `?${query}` : ""}`);
    },
  });
}

export function usePatchCompiledRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch<CompiledRuleSummary>(`/compiled-rules/${encodeURIComponent(id)}`, { active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["compiled-rules"] }),
  });
}

// Apercu d'un onglet Excel (pour piloter le mapping des colonnes).
export type SheetInfo = { name: string; header_row: number; rows: string[][] };

/** POST /rules/inspect — onglets + grille d'apercu + ligne d'en-tete detectee. */
export async function rulesInspect(file: File): Promise<{ sheets: SheetInfo[] }> {
  const fd = new FormData();
  fd.append("file", file);
  return api.upload<{ sheets: SheetInfo[] }>("/rules/inspect", fd);
}

export type ChecklistImportOpts = {
  mode: "replace" | "add";
  sheet?: string;
  header_row?: number;
  topic?: number | null;
  check?: number | null;
  handling?: number | null;
  severity?: number | null;
  zone?: number | null;
  context?: number[];
};

/** POST /rules/import — mapping optionnel (sinon auto-detection cote backend). */
export async function importChecklist(
  file: File,
  opts: ChecklistImportOpts,
): Promise<ChecklistImportResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", opts.mode);
  if (opts.sheet) fd.append("sheet", opts.sheet);
  const mapping: Record<string, unknown> = {};
  if (opts.check != null) {
    mapping.check = opts.check;
    if (opts.header_row != null) mapping.header_row = opts.header_row;
    if (opts.topic != null) mapping.topic = opts.topic;
    if (opts.handling != null) mapping.handling = opts.handling;
    if (opts.severity != null) mapping.severity = opts.severity;
    if (opts.zone != null) mapping.zone = opts.zone;
    if (opts.context && opts.context.length) mapping.context = opts.context;
  }
  if (Object.keys(mapping).length) fd.append("mapping", JSON.stringify(mapping));
  return api.upload<ChecklistImportResult>("/rules/import", fd);
}

export function useValidateAllRules() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ activated: number }>("/rules/validate-all", {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      qc.invalidateQueries({ queryKey: ["compiled-rules"] });
    },
  });
}
