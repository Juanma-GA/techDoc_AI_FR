// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { wizardApi } from "../lib/api";
import { WizardZipDownloadButton } from "./WizardZipDownloadButton";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue ?? key,
  }),
}));

let root: Root | undefined;
let container: HTMLDivElement | undefined;
type ResponseStub = {
  ok: boolean;
  status: number;
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
  return container.querySelector<HTMLButtonElement>("button[aria-busy]");
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
        status: 409,
        statusText: "Conflict",
        json: async () => ({
          code: "ZIP_EXPORT_FAILED",
          message: "ZIP export impossible",
          request_id: "",
        }),
        headers: {
          get: (name) => name === "Content-Type" ? "application/json" : name === "X-Request-Id" ? "" : null,
        },
        blob: async () => new Blob(),
      });
      await pendingResponse;
      await Promise.resolve();
    });
    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("ZIP export impossible");
    expect(button?.disabled).toBe(false);
  });

  it("downloads the ZIP blob when the server responds successfully", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'attachment; filename="archive.zip"' },
      status: 200,
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
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
      "/api/v1/documents/synthetic-document/wizard/zip",
    );
    expect(clickAnchor).toHaveBeenCalledOnce();
    expect(button?.textContent).toBe("migration.generate.zip");
  });

  it("sends the selected size and image format with the ZIP request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => null },
      status: 200,
      json: async () => ({}),
      blob: async () => new Blob(["synthetic zip"]),
      statusText: "OK",
    } satisfies ResponseStub));
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:synthetic"),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const button = mount();
    const sizeInput = container?.querySelector<HTMLInputElement>('input[type="number"]');
    const formatSelect = container?.querySelector<HTMLButtonElement>('button[aria-haspopup="listbox"]');

    await act(async () => {
      if (sizeInput && formatSelect) {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
          ?.set?.call(sizeInput, "640");
        sizeInput.dispatchEvent(new Event("input", { bubbles: true }));
        formatSelect.click();
      }
    });
    const pngOption = [...document.body.querySelectorAll<HTMLButtonElement>('[role="option"]')]
      .find((option) => option.textContent?.includes("migration.generate.imageFormatPng"));
    await act(async () => pngOption?.click());
    await act(async () => {
      button?.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    const expectedUrl =
      "/api/v1/documents/synthetic-document/wizard/zip?max_dimension=640&image_format=png";
    expect(wizardApi.zipUrl("synthetic-document", {
      maxDimension: 640,
      format: "png",
    })).toBe(expectedUrl);
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(expectedUrl);
  });

  it("blocks a non-positive image size", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const button = mount();
    const sizeInput = container?.querySelector<HTMLInputElement>('input[type="number"]');

    await act(async () => {
      if (sizeInput) {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
          ?.set?.call(sizeInput, "0");
        sizeInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });

    expect(button?.disabled).toBe(true);
    expect(container?.querySelector('[role="alert"]')?.textContent).toBe(
      "migration.generate.imageSizeInvalid",
    );
    expect(fetchMock).not.toHaveBeenCalled();
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
