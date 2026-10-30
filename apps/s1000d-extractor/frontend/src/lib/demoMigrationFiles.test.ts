import { afterEach, describe, expect, it, vi } from "vitest";

import { loadDemoMigrationFiles } from "./demoMigrationFiles";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadDemoMigrationFiles", () => {
  it("loads the three sample assets as named files", async () => {
    const requests: { url: string; cache: RequestCache | undefined }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({ url: String(input), cache: init?.cache });
        return new Response(new Blob(["synthetic demo fixture"]));
      }),
    );

    const files = await loadDemoMigrationFiles();

    expect(files.document.name).toBe("WEG-WMO.pdf");
    expect(files.dmrl.name).toBe("DMRL_v2.xlsx");
    expect(files.dm_header.name).toBe("dm_header_template.example.json");
    expect(requests).toEqual([
      `${import.meta.env.BASE_URL}demo/WEG-WMO.pdf`,
      `${import.meta.env.BASE_URL}demo/DMRL_v2.xlsx`,
      `${import.meta.env.BASE_URL}demo/dm_header_template.example.json`,
    ].map((url) => ({
      url,
      cache: "no-store",
    })));
  });

  it("reports missing sample assets instead of returning partial files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 404 })),
    );

    await expect(loadDemoMigrationFiles()).rejects.toThrow("HTTP 404");
  });
});
