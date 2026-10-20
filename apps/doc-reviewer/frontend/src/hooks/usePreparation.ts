import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type {
  OcrPageResult,
  OcrProvider,
  OcrProviderInfo,
  PreparationPageDecision,
  PreparationState,
} from "../types/preparation";

export function usePreparationState(documentId: string | undefined) {
  return useQuery({
    queryKey: ["preparation", documentId],
    queryFn: () => api.get<PreparationState>(`/documents/${documentId}/preparation`),
    enabled: !!documentId,
  });
}

export function useOcrProviders(documentId: string | undefined) {
  return useQuery({
    queryKey: ["preparation", documentId, "ocr-providers"],
    queryFn: () => api.get<OcrProviderInfo[]>(`/documents/${documentId}/preparation/ocr/providers`),
    enabled: !!documentId,
  });
}

export function useOcrPageResult(
  documentId: string | undefined,
  page: number | null,
  provider: OcrProvider | null,
  available: boolean,
) {
  return useQuery({
    queryKey: ["preparation", documentId, "ocr", provider, page],
    queryFn: () =>
      api.get<OcrPageResult>(
        `/documents/${documentId}/preparation/ocr/pages/${page}?provider=${provider}`,
      ),
    enabled: Boolean(documentId && page && provider && available),
  });
}

function usePreparationMutation<TInput, TOutput>(
  documentId: string | undefined,
  mutationFn: (input: TInput) => Promise<TOutput>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["preparation", documentId] });
    },
  });
}

export function useSelectOcrProvider(documentId: string | undefined) {
  return usePreparationMutation<{ provider: OcrProvider }, { selected_provider: OcrProvider }>(
    documentId,
    (body) =>
      api.patch<{ selected_provider: OcrProvider }>(
        `/documents/${documentId}/preparation/provider`,
        body,
      ),
  );
}

export function usePatchPageReadability(documentId: string | undefined) {
  return usePreparationMutation<{ page: number; needs_ocr: boolean }, { page: number }>(
    documentId,
    ({ page, needs_ocr }) =>
      api.patch<{ page: number }>(
        `/documents/${documentId}/preparation/pages/${page}`,
        { needs_ocr },
      ),
  );
}

export function useRunOcrPage(documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ page, provider }: { page: number; provider: OcrProvider }) =>
      api.post<OcrPageResult>(
        `/documents/${documentId}/preparation/ocr/pages/${page}`,
        { provider },
      ),
    onSuccess: (_result, variables) => {
      void qc.invalidateQueries({ queryKey: ["preparation", documentId] });
      void qc.invalidateQueries({
        queryKey: ["preparation", documentId, "ocr", variables.provider, variables.page],
      });
    },
  });
}

export function useValidateOcrPage(documentId: string | undefined) {
  return usePreparationMutation<
    { page: number; provider: OcrProvider; validated: boolean },
    { page: number; validated: boolean }
  >(
    documentId,
    ({ page, provider, validated }) =>
      api.patch<{ page: number; validated: boolean }>(
        `/documents/${documentId}/preparation/ocr/pages/${page}/validation`,
        { provider, validated },
      ),
  );
}

export function useImportPreparationChecklist(documentId: string | undefined) {
  return usePreparationMutation<File, { imported: number; unsupported: number }>(
    documentId,
    async (file) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<{ imported: number; unsupported: number }>(
        `/documents/${documentId}/preparation/checklist`,
        form,
      );
    },
  );
}

export function useDetectPreparationPages(documentId: string | undefined) {
  return usePreparationMutation<void, PreparationPageDecision[]>(
    documentId,
    () => api.post<PreparationPageDecision[]>(`/documents/${documentId}/preparation/detect`),
  );
}

export function usePatchPreparationDecision(documentId: string | undefined) {
  return usePreparationMutation<
    { page: number; is_modified: boolean },
    { decisions: PreparationPageDecision[] }
  >(
    documentId,
    ({ page, is_modified }) =>
      api.patch<{ decisions: PreparationPageDecision[] }>(
        `/documents/${documentId}/preparation/decisions/${page}`,
        { is_modified },
      ),
  );
}

export function useSyncPreparationAnnotations(documentId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ created: string[] }>(
      `/documents/${documentId}/preparation/toc-annotations`,
    ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suggestions", documentId] });
    },
  });
}
