import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../lib/api";
import type { Document } from "../types/domain";

export type BatchUploadResult = {
  created: Document[];
  failed: { filename: string; code: string; message: string }[];
  ignored: string[];
};

type UploadDocumentVariables = {
  file: File;
  target: "metric" | "imperial" | "auto" | "none";
  standardVersionIds?: string[];
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

export type DocumentExport = {
  kind: "original" | "corrected" | "commented" | "converted";
  format: "pdf" | "docx" | "doc";
  label: string;
  warning: string;
};

export type DocumentExports = {
  source_format: "pdf" | "doc" | "docx";
  working_format: "pdf" | "docx";
  has_applied_edits: boolean;
  available: DocumentExport[];
};

export function useDocumentExports(id: string | undefined) {
  return useQuery({
    queryKey: ["document", id, "exports"],
    queryFn: () => api.get<DocumentExports>(`/documents/${id}/exports`),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation<Document | BatchUploadResult, Error, UploadDocumentVariables>({
    // Cle stable : permet de retrouver l'etat "upload en cours" via
    // `useIsMutating` (cache global TanStack Query) meme si le composant qui
    // a lance l'upload a ete demonte entre-temps (navigation puis retour sur
    // la page) — l'upload continue reellement en arriere-plan cote serveur
    // (requete non annulee par un changement de route SPA), seul l'etat
    // local du composant se perdait sans ca.
    mutationKey: ["upload-document"],
    mutationFn: ({
      file,
      target,
      standardVersionIds,
    }: UploadDocumentVariables) => {
      const params = new URLSearchParams({ target });
      // Le backend attend une chaine CSV `standard_version_ids=id1,id2`
      // (Query Optional[str], split sur ","), pas des params repetes.
      const ids = (standardVersionIds ?? []).filter(Boolean);
      if (ids.length > 0) params.set("standard_version_ids", ids.join(","));
      const fd = new FormData();
      // Les .zip passent par /documents/batch ; un fichier unique passe par
      // /documents, qui choisit automatiquement son format de travail.
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

export type DocxBlock = {
  target_id: string;
  index: number;
  page: number;
  zone: string;
  // Zone sémantique CMM (highlights_table / fiche_suiveuse / lep / title_page…).
  semantic_zone: string;
  kind: string;
  text: string;
  table_label: string;
  // Suivi de modifications Word (Phase 2).
  revised: boolean;
  revision_kind: string;
};

/** Vue blocs d'un document Word natif (reviewer docx). */
export function useDocxBlocks(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["document", id, "blocks"],
    queryFn: () => api.get<{ blocks: DocxBlock[] }>(`/documents/${id}/blocks`),
    enabled: !!id && enabled,
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export type DocumentMetaPatch = {
  meta_revision_date?: string | null;
  meta_cmm_number?: string | null;
  meta_first_issue_date?: string | null;
  meta_revision_number?: string | null;
  document_language?: "fr" | "en" | null;
};

/** Mapping manuel par document (repris par les consignes de checklist qui
 * y font reference lors du scan IA). */
export function usePatchDocumentMeta(id: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DocumentMetaPatch) => api.patch<Document>(`/documents/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["document", id] }),
  });
}
