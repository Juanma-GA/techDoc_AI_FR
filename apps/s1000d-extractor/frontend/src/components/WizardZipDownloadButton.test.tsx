// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { wizardApi } from "../lib/api";
import { WizardZipDownloadButton } from "./WizardZipDownloadButton";

vi.mock("../lib/api", () => ({
  wizardApi: {
    zipUrl: (
      docId: string,
      options: {
        maxDimension?: number;
        format?: "original" | "jpeg" | "png";
      } = {},
    ) => {
      const query = new URLSearchParams();
      if (options.maxDimension !== undefined) {
        query.set("max_dimension", String(options.maxDimension));
      }
      if (options.format && options.format !== "original") {
        query.set("image_format", options.format);
      }
      const suffix = query.toString();
      return `/api/v1/documents/${docId}/wizard/zip${suffix ? `?${suffix}` : ""}`;
    },
  },
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

  it("sends the selected size and image format with the ZIP request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => null },
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
    const formatSelect = container?.querySelector<HTMLSelectElement>("select");

    await act(async () => {
      if (sizeInput && formatSelect) {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
          ?.set?.call(sizeInput, "640");
        sizeInput.dispatchEvent(new Event("input", { bubbles: true }));
        formatSelect.value = "png";
        formatSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
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
    expect(fetch).toHaveBeenCalledWith(expectedUrl);
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
