export const MAX_FILE_SIZE = 250 * 1024 * 1024;

export type PDFFileMetadata = Pick<File, "name" | "type" | "size">;

export function validatePDFFile(file: PDFFileMetadata): string | null {
  if (file.size > MAX_FILE_SIZE) {
    return `« ${file.name} » dépasse la limite de 250 Mo.`;
  }
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    return `« ${file.name} » n'est pas un fichier PDF.`;
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} o`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} Ko`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}
