import { afterEach, describe, expect, it, vi } from "vitest";

import { DEMO_PDF_FILENAME, loadDemoPdf } from "./demoPdf";

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
});
