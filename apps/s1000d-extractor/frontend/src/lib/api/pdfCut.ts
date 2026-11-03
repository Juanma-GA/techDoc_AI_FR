import { api, API_BASE } from "./client";
import type { PdfCutDetection } from "./types";

export const pdfCutApi = {
  detect: (docId: string, title?: string) =>
    api<PdfCutDetection>(`/documents/${docId}/pdf-cut/detect`, {
      method: "POST", body: JSON.stringify(title ? { title } : {}),
    }),
  confirm: (docId: string, startPage: number, endPage: number) =>
    api<{ page: number; start_page: number; end_page: number; page_count: number; status: string }>(
      `/documents/${docId}/pdf-cut/confirm`,
      { method: "POST", body: JSON.stringify({ start_page: startPage, end_page: endPage }) },
    ),
  previewUrl: (docId: string, page: number) =>
    `${API_BASE}/documents/${docId}/pdf-cut/preview/${page}`,
};
