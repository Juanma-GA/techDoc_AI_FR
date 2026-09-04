import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { RejectionsSummary, Suggestion, SuggestionStatus } from "../types/domain";

export function useSuggestions(documentId: string | undefined) {
  return useQuery({
    queryKey: ["suggestions", documentId],
    queryFn: () => api.get<Suggestion[]>(`/documents/${documentId}/suggestions`),
    enabled: !!documentId,
  });
}

/** Synthèse IA des rejets (agrégat par règle + paragraphe Mistral). */
export function useRejectionsSummary() {
  return useQuery({
    queryKey: ["suggestions", "rejections-summary"],
    queryFn: () =>
      api.get<RejectionsSummary>("/suggestions/rejections-summary?synthesize=true"),
  });
}

export function usePatchSuggestion(documentId: string | undefined) {
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

export function useBulkStatus(documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: SuggestionStatus }) =>
      api.post<{ updated: number; status: string }>("/suggestions/bulk-status", {
        ids,
        status,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suggestions"] }),
  });
}
