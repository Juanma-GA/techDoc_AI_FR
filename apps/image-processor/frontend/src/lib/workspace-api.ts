import { api, apiDelete, type ExcelColumnDto, type ExcelPieceDto, type OcrResultDto } from "./api";

export type StoredFile = { name: string; data_url: string; sha256?: string };
export type ReplacementPair = {
  id: number;
  reference: string;
  replacement: string;
  enabled: boolean;
};
export type ExcelPreset = {
  workbook: StoredFile | null;
  sheets: string[];
  sheet: string;
  columns: ExcelColumnDto[];
  referenceColumn: string;
  replacementColumn: string;
  icnColumn: string;
  pieceColumn: string;
  pieces: ExcelPieceDto[];
};
export type ExcelSnapshot = ExcelPreset & { pieceRow: string; pairs: ReplacementPair[] };
export type EditKind = "ocr" | "brush-lama" | "brush-color";
export type ImageRevision = {
  image: StoredFile;
  analysis: Omit<OcrResultDto, "edited_image"> | null;
  kind: EditKind;
};
export type Operation = { kind: EditKind | "undo"; at: string };
export type WorkspaceSnapshot = {
  schema_version: 1;
  output_filename?: string;
  image: StoredFile;
  excel: ExcelSnapshot;
  manualPairs: ReplacementPair[];
  revisions: ImageRevision[];
  operations: Operation[];
};
export type HistorySummary = {
  id: string;
  filename: string;
  piece_name: string;
  created_at: string;
  updated_at: string;
  version: number;
  operation_count: number;
};
export type HistoryDetail = HistorySummary & { state: WorkspaceSnapshot };
export type HistoryPage = { items: HistorySummary[]; next_cursor: string | null };

export const workspaceApi = {
  readExcel: () => api<ExcelPreset>("/image-processor/workspace/excel"),
  saveExcel: (state: ExcelPreset) =>
    api<ExcelPreset>("/image-processor/workspace/excel", {
      method: "PUT",
      body: JSON.stringify(state),
    }),
  list: (cursor: string | null) =>
    api<HistoryPage>(`/image-processor/history${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
  read: (id: string) => api<HistoryDetail>(`/image-processor/history/${id}`),
  save: (id: string, state: WorkspaceSnapshot) =>
    api<HistorySummary>(`/image-processor/history/${id}`, {
      method: "PUT",
      body: JSON.stringify(state),
    }),
  remove: (id: string) => apiDelete(`/image-processor/history/${id}`),
};

const storedFiles = new WeakMap<File, Promise<StoredFile>>();

export function storeFile(file: File): Promise<StoredFile> {
  const cached = storedFiles.get(file);
  if (cached) return cached;
  const stored = new Promise<StoredFile>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Unable to read the local file."));
        return;
      }
      resolve({ name: file.name, data_url: reader.result });
    };
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read the local file."));
    reader.readAsDataURL(file);
  }).catch((error: unknown) => {
    storedFiles.delete(file);
    throw error;
  });
  storedFiles.set(file, stored);
  return stored;
}

export function restoreFile(file: StoredFile): File {
  const separator = file.data_url.indexOf(",");
  const header = file.data_url.slice(0, separator);
  const binary = atob(file.data_url.slice(separator + 1));
  const type = header.slice(5).replace(/;base64$/, "");
  return new File([Uint8Array.from(binary, (character) => character.charCodeAt(0))], file.name, { type });
}

export function requestError(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error &&
      typeof error.message === "string") return error.message;
  return fallback;
}
