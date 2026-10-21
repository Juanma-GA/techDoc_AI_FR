// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { wizardApi } from "../lib/api";
import { WizardZipDownloadButton } from "./WizardZipDownloadButton";

vi.mock("../lib/api", () => ({
  wizardApi: { zipUrl: (docId: string) => `/api/v1/documents/${docId}/wizard/zip` },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

let root: Root | undefined;
let container: HTMLDivElement | undefined;
type ResponseStub = {
  ok: boolean;
  statusText: string;
  headers: { get: (name: string) => string | null };
  json: () => Promise<unknown>;
  blob: () => Promise<Blob>;
};

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
    value: true,
    configurable: true,
  });
});

afterEach(() => {
  if (root) act(() => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function mount(disabled = false) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  act(() => {
    root?.render(
      createElement(WizardZipDownloadButton, {
        docId: "synthetic-document",
        disabled,
      }),
    );
  });
  return container.querySelector("button");
}

describe("wizard ZIP download button", () => {
  it("shows progress while downloading and reports API errors", async () => {
    let resolveResponse: (response: ResponseStub) => void = () => {};
    const pendingResponse = new Promise<ResponseStub>((resolve) => {
      resolveResponse = resolve;
    });
    vi.stubGlobal("fetch", vi.fn(() => pendingResponse));
    const button = mount();

    await act(async () => {
      button?.click();
      await Promise.resolve();
    });
    expect(button?.disabled).toBe(true);
    expect(button?.textContent).toBe("migration.analysis.processing");

    await act(async () => {
      resolveResponse({
        ok: false,
        statusText: "Conflict",
        json: async () => ({ message: "ZIP export impossible" }),
        headers: { get: () => null },
        blob: async () => new Blob(),
      });
      await pendingResponse;
      await Promise.resolve();
    });
    expect(container?.querySelector('[role="alert"]')?.textContent).toBe(
      "ZIP export impossible",
    );
    expect(button?.disabled).toBe(false);
  });

  it("downloads the ZIP blob when the server responds successfully", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'attachment; filename="archive.zip"' },
      json: async () => ({}),
      blob: async () => new Blob(["synthetic zip"]),
      statusText: "OK",
    } satisfies ResponseStub));
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:synthetic"),
      revokeObjectURL: vi.fn(),
    });
    const clickAnchor = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const button = mount();

    await act(async () => {
      button?.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(wizardApi.zipUrl("synthetic-document")).toBe(
      "/api/v1/documents/synthetic-document/wizard/zip",
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/documents/synthetic-document/wizard/zip",
    );
    expect(clickAnchor).toHaveBeenCalledOnce();
    expect(button?.textContent).toBe("migration.generate.zip");
  });

  it("does not request an archive while disabled", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const button = mount(true);

    await act(async () => {
      button?.click();
    });

    expect(button?.disabled).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
