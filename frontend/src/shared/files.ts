export const MAX_FILE_SIZE = 250 * 1024 * 1024;

export type PDFFileMetadata = Pick<File, "name" | "type" | "size">;

export type PDFValidationMessages = {
  tooLarge: (name: string) => string;
  notPdf: (name: string) => string;
};

const defaultValidationMessages: PDFValidationMessages = {
  tooLarge: (name) => `« ${name} » dépasse la limite de 250 Mo.`,
  notPdf: (name) => `« ${name} » n'est pas un fichier PDF.`,
};

export function validatePDFFile(
  file: PDFFileMetadata,
  messages: PDFValidationMessages = defaultValidationMessages,
): string | null {
  if (file.size > MAX_FILE_SIZE) {
    return messages.tooLarge(file.name);
  }
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    return messages.notPdf(file.name);
  }
  return null;
}

export function formatFileSize(bytes: number, language = "fr"): string {
  const isEnglish = language.toLowerCase().startsWith("en");
  const units = isEnglish ? ["B", "KB", "MB"] : ["o", "Ko", "Mo"];
  if (bytes < 1024) {
    return `${bytes} ${units[0]}`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} ${units[1]}`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} ${units[2]}`;
}
