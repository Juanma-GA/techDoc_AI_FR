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
