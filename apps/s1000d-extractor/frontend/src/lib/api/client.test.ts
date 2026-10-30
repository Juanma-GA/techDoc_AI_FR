import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiBlob, apiForm, ApiRequestError, request } from "./client";
import { startWizardStream } from "./wizard";

afterEach(() => vi.unstubAllGlobals());

describe("common API transport", () => {
  it("uses a fresh request id and no Content-Type for each GET", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await request("/first");
    await request("/second", { headers: { "X-Test": "kept" } });
    const first = new Headers(fetch.mock.calls[0]?.[1]?.headers);
    const second = new Headers(fetch.mock.calls[1]?.[1]?.headers);
    expect(first.get("X-Request-Id")).toMatch(/^[a-f0-9-]{36}$/);
    expect(first.get("X-Request-Id")).not.toBe(second.get("X-Request-Id"));
    expect(first.has("Content-Type")).toBe(false);
    expect(second.get("X-Test")).toBe("kept");
  });
  it("does not override multipart boundaries and exposes reuse metadata", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response('{"id":"same"}', { headers: { "X-Reused": "true" } }));
    vi.stubGlobal("fetch", fetch);
    const body = new FormData();
    body.append("file", new File(["synthetic"], "source.pdf"));
    expect(await apiForm<{ id: string }>("/documents", body)).toEqual({ id: "same", reused: true });
    expect(new Headers(fetch.mock.calls[0]?.[1]?.headers).has("Content-Type")).toBe(false);
  });
  it("preserves structured errors and displays the response request id", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      code: "BAD_ISSUE", message: "Synthetic failure", request_id: "response-id",
    }), { status: 422, headers: { "Content-Type": "application/json" } })));
    await expect(api("/bad")).rejects.toMatchObject({
      status: 422, code: "BAD_ISSUE", requestId: "response-id",
      message: "Synthetic failure [response-id]",
    });
  });
  it("handles empty responses and preserves download filenames", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response("<dmodule/>", { headers: {
        "Content-Type": "application/xml", "Content-Disposition": 'attachment; filename="DMC-SYNTHETIC.xml"',
      } }));
    vi.stubGlobal("fetch", fetch);
    expect(await api<void>("/empty")).toBeUndefined();
    const file = await apiBlob("/xml");
    expect(file.name).toBe("DMC-SYNTHETIC.xml");
    expect(await file.text()).toBe("<dmodule/>");
  });
  it("rejects malformed or incomplete wizard completion events", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("event: done\ndata: invalid\n\n")));
    await expect(startWizardStream("synthetic", vi.fn())).rejects.toMatchObject({
      code: "INVALID_STREAM", requestId: expect.any(String),
    });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      'event: done\ndata: {"step":"unknown","dms":[]}\n\n',
      { headers: { "Content-Type": "text/event-stream" } },
    )));
    await expect(startWizardStream("synthetic", vi.fn())).rejects.toBeInstanceOf(ApiRequestError);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      'event: progress\ndata: {"pct":20}\n\n',
      { headers: { "Content-Type": "text/event-stream" } },
    )));
    await expect(startWizardStream("synthetic", vi.fn())).rejects.toMatchObject({ code: "INCOMPLETE_STREAM" });
  });
});
