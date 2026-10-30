import { createInstance } from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  processPDF,
  validateExportFileName,
  type ExportDestination,
} from "./api";

describe("validateExportFileName", () => {
  it("accepts a portable PDF or archive filename", () => {
    expect(validateExportFileName("résultat final.pdf")).toBeNull();
    expect(validateExportFileName("documents.zip")).toBeNull();
  });

  it("rejects empty names, paths, and platform-reserved names", () => {
    expect(validateExportFileName("  ")).toBe("required");
    expect(validateExportFileName("C:\\exports\\report.pdf")).toBe("invalidName");
    expect(validateExportFileName("CON.pdf")).toBe("invalidName");
  });
});

describe("processPDF destination", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("writes to the selected destination without starting a browser download", async () => {
    vi.stubGlobal("XMLHttpRequest", MockXMLHttpRequest);
    const write = vi.fn(async (_blob: Blob) => undefined);
    const close = vi.fn(async () => undefined);
    const destination: ExportDestination = {
      name: "chosen.pdf",
      createWritable: async () => ({ write, close }),
    };

    const savedName = await processPDF(
      "merge",
      new FormData(),
      "merged.pdf",
      createInstance().getFixedT("en"),
      undefined,
      destination,
    );

    expect(savedName).toBe("chosen.pdf");
    expect(write).toHaveBeenCalledOnce();
    expect(close).toHaveBeenCalledOnce();
  });
});

class MockXMLHttpRequest {
  static HEADERS_RECEIVED = 2;

  readyState = 0;
  status = 200;
  responseType = "";
  response = new Blob(["synthetic PDF"], { type: "application/pdf" });
  upload: Record<string, unknown> = {};
  onreadystatechange: (() => void) | null = null;
  onprogress: (() => void) | null = null;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  open(): void {}

  getResponseHeader(): string {
    return "application/pdf";
  }

  send(): void {
    this.readyState = 4;
    this.onload?.();
  }
}
