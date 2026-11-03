import { API_BASE, api, apiForm } from "./client";
import type { ResourceKind, ResourceUploadDto } from "./types";

// Ressources client optionnelles : DMRL, CIR, regles BREX et template d'en-tete.
export const resourcesApi = {
  remove: (docId: string, kind: ResourceKind) =>
    api<ResourceUploadDto>(`/documents/${docId}/resources/${kind}`, { method: "DELETE" }),
  upload: async (docId: string, kind: ResourceKind, file: File): Promise<ResourceUploadDto & { reused?: boolean }> => {
    const fd = new FormData();
    fd.append("file", file);
    return apiForm<ResourceUploadDto>(`/documents/${docId}/resources/${kind}`, fd);
  },
  pmcUrl: (docId: string) => `${API_BASE}/documents/${docId}/pmc`,
};
