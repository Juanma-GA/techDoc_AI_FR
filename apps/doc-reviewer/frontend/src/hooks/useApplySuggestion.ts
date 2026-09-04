import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import { useViewerStore } from "../stores/viewerStore";
import type { SuggestionApplyResult, SuggestionGroupApplyResult } from "../types/domain";

export function useApplySuggestion(documentId: string | undefined) {
  const qc = useQueryClient();
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  return useMutation({
    mutationFn: (id: string) => api.post<SuggestionApplyResult>(`/suggestions/${id}/apply`),
    onSuccess: (data) => {
      setPdfVersion(data.new_version);
      qc.invalidateQueries({ queryKey: ["document", documentId] });
      qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
    },
  });
}

/** Apply the same anomaly across every page where it was detected. */
export function useApplyGroup(documentId: string | undefined) {
  const qc = useQueryClient();
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  return useMutation({
    mutationFn: (id: string) =>
      api.post<SuggestionGroupApplyResult>(`/suggestions/${id}/apply-group`),
    onSuccess: (data) => {
      setPdfVersion(data.new_version);
      qc.invalidateQueries({ queryKey: ["document", documentId] });
      qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
    },
  });
}

export function useRevertSuggestion(documentId: string | undefined) {
  const qc = useQueryClient();
  const setPdfVersion = useViewerStore((s) => s.setPdfVersion);
  return useMutation({
    mutationFn: (id: string) => api.post<SuggestionApplyResult>(`/suggestions/${id}/revert`),
    onSuccess: (data) => {
      setPdfVersion(data.new_version);
      qc.invalidateQueries({ queryKey: ["document", documentId] });
      qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
    },
  });
}
