import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useDemoMode: vi.fn(),
  loadDemoPdf: vi.fn(),
}));

vi.mock("@internal/ui", () => ({
  useDemoMode: mocks.useDemoMode,
}));
vi.mock("../../lib/demoPdf", () => ({
  loadDemoPdf: mocks.loadDemoPdf,
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { message?: string }) =>
      options?.message ? `${key} ${options.message}` : key,
  }),
}));

import { DemoPdfImportButton } from "./DemoPdfImportButton";

describe("DemoPdfImportButton", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("is hidden in normal mode", async () => {
    mocks.useDemoMode.mockReturnValue({ mode: "normal", isReady: true });

    await act(async () => {
      root.render(<DemoPdfImportButton onFile={vi.fn()} />);
    });

    expect(container.textContent).toBe("");
  });

  it("loads the local demo PDF and sends it through the supplied upload handler", async () => {
    const file = new File(["synthetic"], "DEMO_CMM_PDF_anonyme.pdf", {
      type: "application/pdf",
    });
    const onFile = vi.fn();
    mocks.useDemoMode.mockReturnValue({ mode: "demo", isReady: true });
    mocks.loadDemoPdf.mockResolvedValue(file);

    await act(async () => {
      root.render(<DemoPdfImportButton onFile={onFile} />);
    });

    await act(async () => {
      container.querySelector("button")?.click();
    });

    expect(mocks.loadDemoPdf).toHaveBeenCalledOnce();
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("announces a local PDF loading error", async () => {
    mocks.useDemoMode.mockReturnValue({ mode: "demo", isReady: true });
    mocks.loadDemoPdf.mockRejectedValue(new Error("HTTP 404"));

    await act(async () => {
      root.render(<DemoPdfImportButton onFile={vi.fn()} />);
    });

    await act(async () => {
      container.querySelector("button")?.click();
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "HTTP 404",
    );
  });
});
