import { afterEach, describe, expect, it, vi } from "vitest";

import { comparisonApi } from "./comparisonApi";

describe("comparison multipart upload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends every PDF and the selected reference index as multipart form data", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ id: "comparison-id" })),
    );
    vi.stubGlobal("fetch", fetchMock);
    const first = new File(["%PDF-first"], "first.pdf", { type: "application/pdf" });
    const second = new File(["%PDF-second"], "second.pdf", { type: "application/pdf" });

    await comparisonApi.create([first, second], 1);

    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error("Expected the comparison request to call fetch.");
    const [url, init] = call;
    expect(url).toBe("/api/v1/comparisons");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "X-Requested-With": "doc-reviewer" });
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    const body = init?.body as FormData;
    expect(body.getAll("files")).toHaveLength(2);
    expect(body.get("reference_index")).toBe("1");
  });
});
