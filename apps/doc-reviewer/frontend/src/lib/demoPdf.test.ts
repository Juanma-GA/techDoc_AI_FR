import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEMO_PDF_FILENAME,
  DEMO_REVISION_PDF_FILENAME,
  loadDemoComparisonPdfs,
  loadDemoPdf,
} from "./demoPdf";

describe("loadDemoPdf", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the local PDF as a File for the normal upload flow", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("%PDF-synthetic", {
        status: 200,
        headers: { "content-type": "application/pdf" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = await loadDemoPdf();

    expect(fetchMock).toHaveBeenCalledWith(
      `${import.meta.env.BASE_URL}demo/${DEMO_PDF_FILENAME}`,
    );
    expect(file.name).toBe(DEMO_PDF_FILENAME);
    expect(file.type).toBe("application/pdf");
    expect(file.size).toBe("%PDF-synthetic".length);
    const fileContents = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          resolve(reader.result);
        } else {
          reject(new Error("The demo PDF file could not be read as text"));
        }
      };
      reader.onerror = () =>
        reject(reader.error ?? new Error("The demo PDF file could not be read"));
      reader.readAsText(file);
    });
    expect(fileContents).toBe("%PDF-synthetic");
  });

  it("rejects a missing demo asset", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));

    await expect(loadDemoPdf()).rejects.toThrow("HTTP 404");
  });

  it("rejects an SPA fallback response instead of uploading it as a PDF", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html></html>", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
      ),
    );

    await expect(loadDemoPdf()).rejects.toThrow("Expected application/pdf");
  });

  it("loads both comparison PDFs with the original first", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response("%PDF-synthetic", {
        headers: { "content-type": "application/pdf" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const files = await loadDemoComparisonPdfs();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `${import.meta.env.BASE_URL}demo/${DEMO_PDF_FILENAME}`,
      `${import.meta.env.BASE_URL}demo/${DEMO_REVISION_PDF_FILENAME}`,
    ]);
    expect(files.map((file) => file.name)).toEqual([
      DEMO_PDF_FILENAME,
      DEMO_REVISION_PDF_FILENAME,
    ]);
    expect(files.every((file) => file.type === "application/pdf" && file.size > 0)).toBe(true);
  });

  it("rejects the pair if the revision is missing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) =>
      url.endsWith(DEMO_REVISION_PDF_FILENAME)
        ? new Response(null, { status: 404 })
        : new Response("%PDF-synthetic", {
            headers: { "content-type": "application/pdf" },
          }),
    ));

    await expect(loadDemoComparisonPdfs()).rejects.toThrow("HTTP 404");
  });

  it("rejects an empty revision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(null, { headers: { "content-type": "application/pdf" } }),
    ));

    await expect(loadDemoPdf(DEMO_REVISION_PDF_FILENAME)).rejects.toThrow("The PDF is empty");
  });
});
