import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Document } from "../types/domain";

export type BatchUploadResult = {
  created: Document[];
  failed: { filename: string; code: string; message: string }[];
  ignored: string[];
};

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
      target: "metric" | "imperial" | "auto" | "none";
      // Set de normes cibles actives (Parametres). Le backend accepte un
      // `standard_version_ids` repete et le persiste sur le document.
      standardVersionIds?: string[];
    }) => {
      const params = new URLSearchParams({ target });
      // Le backend attend une chaine CSV `standard_version_ids=id1,id2`
      // (Query Optional[str], split sur ","), pas des params repetes.
      const ids = (standardVersionIds ?? []).filter(Boolean);
      if (ids.length > 0) params.set("standard_version_ids", ids.join(","));
      const fd = new FormData();
      // Les .zip passent par /documents/batch (extraction + conversion Word
      // -> PDF cote serveur) ; un fichier unique passe par /documents.
      if (file.name.toLowerCase().endsWith(".zip")) {
        fd.append("files", file);
        return api.upload<BatchUploadResult>(`/documents/batch?${params.toString()}`, fd);
      }
      fd.append("file", file);
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
