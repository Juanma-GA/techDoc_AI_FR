import { afterEach, describe, expect, it, vi } from "vitest";

import { api, CSRF_HEADERS } from "./api";

function mockFetch() {
  const fetchMock = vi.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function headersOf(init: RequestInit | undefined): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>;
}

function sentHeaders(fetchMock: ReturnType<typeof mockFetch>): Record<string, string> {
  return headersOf(fetchMock.mock.calls[0]?.[1]);
}

describe("api client anti-CSRF header", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends X-Requested-With on JSON mutations", async () => {
    const fetchMock = mockFetch();
    await api.post("/settings/vision", { enabled: true });
    expect(sentHeaders(fetchMock)["X-Requested-With"]).toBe("doc-reviewer");
    expect(sentHeaders(fetchMock)["Content-Type"]).toBe("application/json");
  });

  it("sends X-Requested-With on multipart uploads without forcing a JSON content type", async () => {
    const fetchMock = mockFetch();
    const form = new FormData();
    form.append("file", new Blob(["%PDF-1.4"]), "doc.pdf");
    await api.upload("/documents", form);
    const headers = sentHeaders(fetchMock);
    expect(headers["X-Requested-With"]).toBe("doc-reviewer");
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("sends X-Requested-With on DELETE and PATCH", async () => {
    const fetchMock = mockFetch();
    await api.patch("/documents/1", { meta_cmm_number: "1" });
    await api.delete("/documents/1");
    expect(fetchMock.mock.calls).toHaveLength(2);
    for (const call of fetchMock.mock.calls) {
      expect(headersOf(call[1])["X-Requested-With"]).toBe(CSRF_HEADERS["X-Requested-With"]);
    }
  });
});
