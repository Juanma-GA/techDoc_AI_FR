import { afterEach, describe, expect, it, vi } from "vitest";

import { apiForm, imageReplaceApi } from "./api";
import { storeFile } from "./workspace-api";

afterEach(() => vi.unstubAllGlobals());

describe("JPEG download contract", () => {
  it("uses the server ICN name and binary JPEG, without renaming the working image", async () => {
    const jpeg = new Uint8Array([255, 216, 255, 217]);
    const fetch = vi.fn().mockResolvedValue(new Response(jpeg, { headers: {
      "Content-Type": "image/jpeg",
      "Content-Disposition": "attachment; filename*=UTF-8''ICN-%C3%A9.jpg",
    } }));
    vi.stubGlobal("fetch", fetch);
    const form = new FormData();
    const exported = await imageReplaceApi.exportImage(form);
    expect(exported.filename).toBe("ICN-é.jpg");
    const saved = await storeFile(new File([exported.blob], exported.filename, { type: exported.blob.type }));
    expect(saved.data_url).toBe("data:image/jpeg;base64,/9j/2Q==");
    expect(fetch).toHaveBeenCalledWith("/api/v1/image-processor/export", { method: "POST", body: form });
  });

  const invalidHeaders: HeadersInit[] = [
    { "Content-Type": "image/png", "Content-Disposition": "attachment; filename*=UTF-8''ICN.jpg" },
    { "Content-Type": "image/jpeg" },
    { "Content-Type": "image/jpeg", "Content-Disposition": "attachment; filename*=UTF-8''ICN.png" },
  ];
  it.each(invalidHeaders)("rejects invalid download metadata instead of silently saving a PNG as JPEG", async (headers) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("synthetic", { headers })));
    await expect(imageReplaceApi.exportImage(new FormData())).rejects.toThrow(/invalid JPEG/);
  });

  it("surfaces server export errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(
      { message: "Synthetic export failure." }, { status: 500 },
    )));
    await expect(imageReplaceApi.exportImage(new FormData())).rejects.toThrow("Synthetic export failure.");
  });

  it("preserves readable errors and JSON responses for existing multipart calls", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(Response.json({ detail: "Synthetic selection failure." }, { status: 422 }))
      .mockResolvedValueOnce(Response.json({ pairs: [] }));
    vi.stubGlobal("fetch", fetch);
    await expect(apiForm("/test", new FormData())).rejects.toThrow("Synthetic selection failure.");
    await expect(apiForm("/test", new FormData())).resolves.toEqual({ pairs: [] });
  });

  it("posts a targeted OCR-line replacement as multipart data", async () => {
    const form = new FormData();
    const payload = {
      edited_image: "data:image/jpeg;base64,c3ludGhldGlj",
      replacement_count: 1,
      replacement_font_size: 12,
    };
    const fetch = vi.fn().mockResolvedValue(Response.json(payload));
    vi.stubGlobal("fetch", fetch);

    await expect(imageReplaceApi.replaceLine(form)).resolves.toEqual(payload);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/image-processor/replace-line",
      { method: "POST", body: form },
    );
  });
});
