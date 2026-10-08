import { afterEach, describe, expect, it, vi } from "vitest";

import { ecmAutomationApi } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ecmAutomationApi", () => {
  it("requests a native picker for the selected local path kind", async () => {
    const response = { ok: true, json: async () => ({ path: "C:\\ECM\\ECN.pdf" }) };
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const request = {
      kind: "source_files" as const,
      current_path: "C:\\ECM",
      language: "fr" as const,
    };

    await ecmAutomationApi.browse(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/ecm-automation/browse",
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
      folder_mode: "create" as const,
    };

    await ecmAutomationApi.preview(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/ecm-automation/preview",
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });
});