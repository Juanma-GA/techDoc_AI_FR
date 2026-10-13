import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { RejectionsSummary, RuleResult, Suggestion, SuggestionStatus } from "../types/domain";

export function useSuggestions(documentId: string | undefined) {
  return useQuery({
    queryKey: ["suggestions", documentId],
    queryFn: () => api.get<Suggestion[]>(`/documents/${documentId}/suggestions`),
    enabled: !!documentId,
  });
}

export function useRuleResults(documentId: string | undefined) {
  return useQuery({
    queryKey: ["rule-results", documentId],
    queryFn: () => api.get<RuleResult[]>(`/documents/${documentId}/rule-results`),
    enabled: !!documentId,
  });
}

/** Synthèse IA des rejets (agrégat par règle + paragraphe Mistral). */
export function useRejectionsSummary(synthesize = true) {
  return useQuery({
    queryKey: ["suggestions", "rejections-summary", synthesize],
    queryFn: () =>
      api.get<RejectionsSummary>(`/suggestions/rejections-summary?synthesize=${synthesize}`),
  });
}

export function usePatchSuggestion(_documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      proposedText,
      feedback,
    }: {
      id: string;
      status: SuggestionStatus;
      proposedText?: string;
      feedback?: string;
    }) =>
      api.patch<Suggestion>(`/suggestions/${id}`, {
        status,
        proposed_text: proposedText,
        feedback,
      }),
    // Invalide TOUTES les queries suggestions (prefixe) : la vue document ET
    // les agregats ["suggestions","all"] du Dashboard / Donnees -> un rejet
    // (et son motif) remonte instantanement partout.
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suggestions"] }),
  });
}

export function useBulkStatus(_documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ids, status }: { ids: string[]; status: SuggestionStatus }) => {
      let updated = 0;
      for (let index = 0; index < ids.length; index += 1000) {
        const response = await api.post<{ updated: number; status: string }>(
          "/suggestions/bulk-status",
          { ids: ids.slice(index, index + 1000), status },
        );
        updated += response.updated;
      }
      return { updated, status };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suggestions"] }),
  });
}
