import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { documentsApi, type DocumentDto, type HeaderMeta } from "../lib/api";

export function useDocuments() {
  return useQuery<DocumentDto[]>({ queryKey: ["documents"], queryFn: documentsApi.list });
}

export function useDocument(id: string | null) {
  return useQuery<DocumentDto>({
    queryKey: ["document", id],
    queryFn: () => documentsApi.get(id as string),
    enabled: !!id,
  });
}

export function useUploadDocuments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => documentsApi.upload(files),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => documentsApi.remove(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useSaveHeaderMeta(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (meta: HeaderMeta) => documentsApi.saveHeaderMeta(docId, meta),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["document", docId] });
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useReextract(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => documentsApi.reextract(docId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["items", docId] });
      void qc.invalidateQueries({ queryKey: ["document", docId] });
    },
  });
}
