import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Suggestion, SuggestionStatus } from "../types/domain";

export function useSuggestions(documentId: string | undefined) {
  return useQuery({
    queryKey: ["suggestions", documentId],
    queryFn: () => api.get<Suggestion[]>(`/documents/${documentId}/suggestions`),
    enabled: !!documentId,
  });
}

export function usePatchSuggestion(documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      proposedText,
    }: {
      id: string;
      status: SuggestionStatus;
      proposedText?: string;
    }) =>
      api.patch<Suggestion>(`/suggestions/${id}`, {
        status,
        proposed_text: proposedText,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suggestions", documentId] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suggestions", documentId] }),
  });
}
