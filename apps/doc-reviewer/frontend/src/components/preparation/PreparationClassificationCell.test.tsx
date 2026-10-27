import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { value?: string }) =>
      options?.value ? `${key}:${options.value}` : key,
  }),
}));

import type { PreparationPageDecision } from "../../types/preparation";
import { PreparationClassificationCell } from "./PreparationClassificationCell";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const baseDecision: PreparationPageDecision = {
  page: 3,
  page_type: null,
  is_modified: null,
  decision_status: "no_applicable_rule",
  rule_results: [],
  failures: [],
  review_reasons: [],
  toc_page: null,
  toc_bbox: null,
  page_type_source: "unclassified",
  document_page_source: "auto",
};

describe("PreparationClassificationCell", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onClassification = vi.fn();

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    onClassification.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  function render(decision: PreparationPageDecision): void {
    act(() => {
      root.render(
        <PreparationClassificationCell
          decision={decision}
          pageTypeOptions={["TP1", "TP2"]}
          saving={false}
          onClassification={onClassification}
        />,
      );
    });
  }

  it("flags an unclassified page and keeps save disabled until something changes", () => {
    render(baseDecision);

    expect(container.textContent).toContain("preparationUi.classification.source.unclassified");
    const save = container.querySelector("button") as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });

  it("submits the chosen type and document page", () => {
    render(baseDecision);
    const select = container.querySelector("select") as HTMLSelectElement;
    const input = container.querySelector("input") as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;

    act(() => {
      select.value = "TP2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      setter?.call(input, " 12 ");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    act(() => {
      (container.querySelector("button") as HTMLButtonElement).click();
    });

    expect(onClassification).toHaveBeenCalledWith(3, "TP2", "12");
  });

  it("shows a manual source and detection evidence", () => {
    render({
      ...baseDecision,
      page_type: "TP1",
      page_type_source: "manual",
      document_page: "401",
      document_page_source: "manual",
      classification_evidence: { footer_lines: ["JUL 27/26"], footer_page_key: "Page 401" },
    });

    expect(container.textContent).toContain("preparationUi.classification.source.manual");
    expect(container.textContent).toContain("JUL 27/26");
    expect((container.querySelector("select") as HTMLSelectElement).value).toBe("TP1");
  });
});
