import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Document } from "../types/domain";

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get<Document[]>("/documents"),
  });
}

export function useDocument(id: string | undefined) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => api.get<Document>(`/documents/${id}`),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      target,
      standardVersionId,
    }: {
      file: File;
      target: "metric" | "imperial" | "auto";
      standardVersionId?: string | null;
    }) => {
      const fd = new FormData();
      fd.append("file", file);
      const params = new URLSearchParams({ target });
      if (standardVersionId) params.set("standard_version_id", standardVersionId);
      return api.upload<Document>(`/documents?${params.toString()}`, fd);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}
