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
      standardVersionIds,
    }: {
      file: File;
      target: "metric" | "imperial" | "auto";
      // Set de normes cibles actives (Parametres). Le backend accepte un
      // `standard_version_ids` repete et le persiste sur le document.
      standardVersionIds?: string[];
    }) => {
      const fd = new FormData();
      fd.append("file", file);
      const params = new URLSearchParams({ target });
      // Le backend attend une chaine CSV `standard_version_ids=id1,id2`
      // (Query Optional[str], split sur ","), pas des params repetes.
      const ids = (standardVersionIds ?? []).filter(Boolean);
      if (ids.length > 0) params.set("standard_version_ids", ids.join(","));
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
