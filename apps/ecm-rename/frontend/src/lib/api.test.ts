import { afterEach, describe, expect, it, vi } from "vitest";

import { ecmRenameApi } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ecmRenameApi", () => {
  it("requests a native picker for the selected local path kind", async () => {
    const response = { ok: true, json: async () => ({ path: "C:\\ECM\\ECN.pdf" }) };
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const request = {
      kind: "source_file" as const,
      current_path: "C:\\ECM",
      language: "fr" as const,
    };

    await ecmRenameApi.browse(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/ecm-rename/browse",
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });

  it("sends local input paths to the preview endpoint", async () => {
    const response = { ok: true, json: async () => ({}) };
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const request = {
      source_path: "C:\\ECM\\ECN.pdf",
      tracker_path: "C:\\ECM\\tracker.xlsx",
    };

    await ecmRenameApi.preview(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/ecm-rename/preview",
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });
});