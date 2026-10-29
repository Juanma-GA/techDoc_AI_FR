import { afterEach, describe, expect, it, vi } from "vitest";

import { DEMO_PDF_FILE_NAME, loadDemoPdf } from "./demoPdf";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("demo PDF loader", () => {
  it("loads the named static asset as an in-memory PDF file", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(["%PDF-synthetic"]), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = await loadDemoPdf();

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining(`/demo/${DEMO_PDF_FILE_NAME}`));
    expect(file.name).toBe(DEMO_PDF_FILE_NAME);
    expect(file.type).toBe("application/pdf");
    expect(file.size).toBeGreaterThan(0);
  });

  it("reports when the static asset cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));

    await expect(loadDemoPdf()).rejects.toThrow("HTTP 404");
  });
});
