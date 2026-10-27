import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../lib/api";
import type {
  OcrPageResult,
  OcrProvider,
  OcrProviderInfo,
  PreparationPageText,
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

export function usePreparationNativeText(
  documentId: string | undefined,
  page: number | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["preparation", documentId, "native-text", page],
    queryFn: () =>
      api.get<PreparationPageText>(
        `/documents/${documentId}/preparation/text/pages/${page}`,
      ),
    enabled: Boolean(documentId && page && enabled),
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

export type OcrDocumentProgress = { done: number; total: number };

export function useRunOcrDocument(documentId: string | undefined) {
  const qc = useQueryClient();
  const [progress, setProgress] = useState<OcrDocumentProgress | null>(null);
  const mutation = useMutation({
    mutationFn: async (pages: number[]) => {
      setProgress({ done: 0, total: pages.length });
      for (const [index, page] of pages.entries()) {
        await api.post<OcrPageResult>(
          `/documents/${documentId}/preparation/ocr/pages/${page}`,
          { provider: "mistral" },
        );
        setProgress({ done: index + 1, total: pages.length });
      }
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["preparation", documentId] });
    },
  });
  return {
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    progress,
  };
}

export function useValidateAllOcrPages(documentId: string | undefined) {
  return usePreparationMutation<
    void,
    { provider: "mistral"; validated_pages: number[] }
  >(
    documentId,
    () =>
      api.post<{ provider: "mistral"; validated_pages: number[] }>(
        `/documents/${documentId}/preparation/ocr/validation`,
      ),
  );
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

export function usePatchPageClassification(documentId: string | undefined) {
  return usePreparationMutation<
    { page: number; page_type: string | null; document_page: string | null },
    { decisions: PreparationPageDecision[] }
  >(
    documentId,
    ({ page, page_type, document_page }) =>
      api.patch<{ decisions: PreparationPageDecision[] }>(
        `/documents/${documentId}/preparation/pages/${page}/classification`,
        { page_type, document_page },
      ),
  );
}

export function usePatchAbsentPageTypes(documentId: string | undefined) {
  return usePreparationMutation<
    { page_types: string[]; absent: boolean },
    { absent_page_types: string[] }
  >(
    documentId,
    (body) =>
      api.patch<{ absent_page_types: string[] }>(
        `/documents/${documentId}/preparation/absent-page-types`,
        body,
      ),
  );
}

export function usePatchPreparationMapping(documentId: string | undefined) {
  return usePreparationMutation<
    { mapping: Record<string, unknown> },
    { preparation_mapping: Record<string, unknown> }
  >(
    documentId,
    ({ mapping }) =>
      api.patch<{ preparation_mapping: Record<string, unknown> }>(
        `/documents/${documentId}/preparation/mapping`,
        { mapping },
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
