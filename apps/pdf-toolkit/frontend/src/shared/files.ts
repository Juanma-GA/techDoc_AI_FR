export const MAX_FILE_SIZE = 250 * 1024 * 1024;

export function moveFileInList(files: File[], index: number, offset: -1 | 1): File[] {
  const file = files[index];
  if (!file) throw new RangeError("Invalid file index");
  const target = index + offset;
  if (target < 0 || target >= files.length) return files;
  const updated = [...files];
  updated.splice(index, 1);
  updated.splice(target, 0, file);
  return updated;
}

export type PDFFileMetadata = Pick<File, "name" | "type" | "size">;

export type PDFValidationMessages = {
  tooLarge: (name: string) => string;
  notPdf: (name: string) => string;
};

export type ImageValidationMessages = {
  tooLarge: (name: string) => string;
  notImage: (name: string) => string;
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

export function validateImageFile(
  file: PDFFileMetadata,
  messages: ImageValidationMessages,
): string | null {
  if (file.size > MAX_FILE_SIZE) {
    return messages.tooLarge(file.name);
  }
  const extension = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
  const expectedType = extension === ".png" ? "image/png" : [".jpg", ".jpeg"].includes(extension) ? "image/jpeg" : null;
  if (expectedType === null || (file.type !== "" && file.type !== expectedType)) {
    return messages.notImage(file.name);
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
