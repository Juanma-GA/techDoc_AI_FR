import { describe, expect, it } from "vitest";

import { formatFileSize, MAX_FILE_SIZE, moveFileInList, validateImageFile, validatePDFFile } from "./files";

describe("moveFileInList", () => {
  it("reorders files without mutating the input and preserves boundary behavior", () => {
    const files = [new File(["synthetic"], "first.pdf"), new File(["synthetic"], "second.pdf")];
    expect(moveFileInList(files, 0, 1)).toEqual([files[1], files[0]]);
    expect(files.map((file) => file.name)).toEqual(["first.pdf", "second.pdf"]);
    expect(moveFileInList(files, 0, -1)).toBe(files);
    expect(() => moveFileInList(files, -1, 1)).toThrow(RangeError);
  });
});

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

  it("rejects a file over 500 Mo", () => {
    expect(
      validatePDFFile({
        name: "large.pdf",
        type: "application/pdf",
        size: MAX_FILE_SIZE + 1,
      }),
    ).toContain("500 Mo");
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

  it("formats byte sizes for the English locale", () => {
    expect(formatFileSize(1024, "en")).toBe("1.0 KB");
  });
});

describe("validateImageFile", () => {
  const messages = {
    tooLarge: (name: string) => `too large: ${name}`,
    notImage: (name: string) => `not image: ${name}`,
  };

  it("accepts PNG and JPEG files", () => {
    expect(validateImageFile({ name: "photo.PNG", type: "image/png", size: 10 }, messages)).toBeNull();
    expect(validateImageFile({ name: "photo.jpeg", type: "image/jpeg", size: 10 }, messages)).toBeNull();
  });

  it("rejects unsupported image formats and MIME types", () => {
    expect(validateImageFile({ name: "photo.webp", type: "image/webp", size: 10 }, messages)).toBe(
      "not image: photo.webp",
    );
    expect(validateImageFile({ name: "photo.png", type: "image/jpeg", size: 10 }, messages)).toBe(
      "not image: photo.png",
    );
  });

  it("rejects images over the size limit", () => {
    expect(
      validateImageFile({ name: "large.png", type: "image/png", size: MAX_FILE_SIZE + 1 }, messages),
    ).toBe("too large: large.png");
  });

  it("supports a lower image limit for signatures", () => {
    expect(
      validateImageFile({ name: "signature.png", type: "image/png", size: 11 }, messages, 10),
    ).toBe("too large: signature.png");
  });
});
