import { describe, expect, it } from "vitest";

import { formatFileSize, MAX_FILE_SIZE, validatePDFFile } from "./files";

describe("validatePDFFile", () => {
  it("accepts a PDF at the size limit", () => {
    expect(
      validatePDFFile({
        name: "report.pdf",
        type: "application/pdf",
        size: MAX_FILE_SIZE,
      }),
    ).toBeNull();
  });

  it("rejects a file over 250 Mo", () => {
    expect(
      validatePDFFile({
        name: "large.pdf",
        type: "application/pdf",
        size: MAX_FILE_SIZE + 1,
      }),
    ).toContain("250 Mo");
  });

  it("rejects non-PDF files", () => {
    expect(
      validatePDFFile({
        name: "notes.txt",
        type: "text/plain",
        size: 10,
      }),
    ).toContain("n'est pas un fichier PDF");
  });

  it("formats byte sizes for the file list", () => {
    expect(formatFileSize(128)).toBe("128 o");
    expect(formatFileSize(1024)).toBe("1.0 Ko");
  });
});
