import { DemoModeProvider } from "@internal/ui";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type * as DemoPdf from "../../lib/demoPdf";

const mocks = vi.hoisted(() => ({ loadDemoComparisonPdfs: vi.fn() }));

vi.mock("../../lib/demoPdf", async (importOriginal) => ({
  ...await importOriginal<typeof DemoPdf>(),
  loadDemoComparisonPdfs: mocks.loadDemoComparisonPdfs,
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: { message?: string }) =>
      values?.message ? `${key} ${values.message}` : key,
  }),
}));

import { DEMO_PDF_FILENAME, DEMO_REVISION_PDF_FILENAME } from "../../lib/demoPdf";
import { ComparisonSetupCard } from "./ComparisonSetupCard";

describe("ComparisonSetupCard demo loading", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onCompare = vi.fn();
  const demoFiles = [
    new File(["original"], DEMO_PDF_FILENAME, { type: "application/pdf" }),
    new File(["revision"], DEMO_REVISION_PDF_FILENAME, { type: "application/pdf" }),
  ];

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    vi.resetAllMocks();
    mocks.loadDemoComparisonPdfs.mockResolvedValue(demoFiles);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function render(
    mode: "normal" | "demo" = "demo",
    isReady = true,
    isCreating = false,
  ) {
    await act(async () => root.render(
      <DemoModeProvider mode={mode} isReady={isReady}>
        <ComparisonSetupCard
          onCompare={onCompare}
          isCreating={isCreating}
          createError={null}
        />
      </DemoModeProvider>,
    ));
  }

  function button(label: string): HTMLButtonElement {
    const result = Array.from(container.querySelectorAll("button")).find(
      (element) => element.textContent === label,
    );
    if (!result) throw new Error(`Missing button: ${label}`);
    return result;
  }

  async function selectFiles(files: File[]) {
    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    if (!input) throw new Error("Missing file input");
    Object.defineProperty(input, "files", { configurable: true, value: files });
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it.each([
    { mode: "normal" as const, isReady: true },
    { mode: "demo" as const, isReady: false },
  ])("hides demo loading in mode $mode, ready $isReady", async ({ mode, isReady }) => {
    await render(mode, isReady);

    expect(container.textContent).not.toContain("comparison.loadDemo");
    expect(mocks.loadDemoComparisonPdfs).not.toHaveBeenCalled();
  });

  it("loads both PDFs and selects the original without automatically comparing", async () => {
    await render();
    await act(async () => button("comparison.loadDemo").click());

    expect(container.querySelectorAll(".item-row")).toHaveLength(2);
    expect(container.querySelector<HTMLSelectElement>("select")?.value).toBe("0");
    expect(onCompare).not.toHaveBeenCalled();
    await act(async () => button("comparison.compareButton").click());

    expect(onCompare).toHaveBeenCalledWith(demoFiles, 0);
  });

  it("replaces a previous selection and resets the reference without duplicates", async () => {
    await render();
    await act(async () => button("comparison.loadDemo").click());
    const reference = container.querySelector<HTMLSelectElement>("select");
    if (!reference) throw new Error("Missing reference selector");
    await act(async () => {
      reference.value = "1";
      reference.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await selectFiles([new File(["third"], "third.pdf", { type: "application/pdf" })]);
    expect(container.querySelectorAll(".item-row")).toHaveLength(3);

    await act(async () => button("comparison.loadDemo").click());

    expect(container.querySelectorAll(".item-row")).toHaveLength(2);
    expect(container.querySelector<HTMLSelectElement>("select")?.value).toBe("0");
    expect(container.textContent).not.toContain("third.pdf");
  });

  it("announces loading errors while preserving the previous selection and reference", async () => {
    await render();
    await act(async () => button("comparison.loadDemo").click());
    const reference = container.querySelector<HTMLSelectElement>("select");
    if (!reference) throw new Error("Missing reference selector");
    await act(async () => {
      reference.value = "1";
      reference.dispatchEvent(new Event("change", { bubbles: true }));
    });
    mocks.loadDemoComparisonPdfs.mockRejectedValue(new Error("HTTP 404"));

    await act(async () => button("comparison.loadDemo").click());

    expect(container.querySelector('[role="alert"]')?.textContent).toContain("HTTP 404");
    expect(container.querySelectorAll(".item-row")).toHaveLength(2);
    expect(container.querySelector<HTMLSelectElement>("select")?.value).toBe("1");
    await act(async () => button("comparison.compareButton").click());
    expect(onCompare).toHaveBeenCalledWith(demoFiles, 1);
  });

  it("disables competing actions while demo files are loading", async () => {
    await render();
    await act(async () => button("comparison.loadDemo").click());
    let finish: (files: File[]) => void = () => { throw new Error("Missing resolver"); };
    mocks.loadDemoComparisonPdfs.mockReturnValue(new Promise<File[]>((resolve) => {
      finish = resolve;
    }));

    await act(async () => button("comparison.loadDemo").click());

    expect(button("comparison.demoLoading").disabled).toBe(true);
    expect(button("comparison.demoLoading").getAttribute("aria-busy")).toBe("true");
    expect(button("comparison.compareButton").disabled).toBe(true);
    expect(button("comparison.removeFile").disabled).toBe(true);
    expect(container.querySelector<HTMLSelectElement>("select")?.disabled).toBe(true);
    await selectFiles([new File(["third"], "third.pdf", { type: "application/pdf" })]);
    expect(container.querySelectorAll(".item-row")).toHaveLength(2);
    expect(container.textContent).not.toContain("third.pdf");

    await act(async () => finish(demoFiles));
    expect(button("comparison.loadDemo").disabled).toBe(false);
    expect(button("comparison.compareButton").disabled).toBe(false);
  });

  it("does not allow demo loading during comparison creation", async () => {
    await render("demo", true, true);

    expect(button("comparison.loadDemo").disabled).toBe(true);
    await act(async () => button("comparison.loadDemo").click());
    expect(mocks.loadDemoComparisonPdfs).not.toHaveBeenCalled();
  });

  it("preserves manual multiple-file selection in normal mode", async () => {
    await render("normal");
    await selectFiles(demoFiles);
    await act(async () => button("comparison.compareButton").click());

    expect(onCompare).toHaveBeenCalledWith(demoFiles, 0);
    expect(mocks.loadDemoComparisonPdfs).not.toHaveBeenCalled();
  });
});
