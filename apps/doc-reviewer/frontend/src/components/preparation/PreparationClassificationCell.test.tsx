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

  function render(
    decision: PreparationPageDecision,
    pageTitleOptions: { title: string; page_type: string }[] = [],
  ): void {
    act(() => {
      root.render(
        <PreparationClassificationCell
          decision={decision}
          pageTypeOptions={["TP1", "TP2"]}
          pageTitleOptions={pageTitleOptions}
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

  it("submits the chosen page type without a document-page input", () => {
    render(baseDecision);
    const select = container.querySelector("select") as HTMLSelectElement;

    act(() => {
      select.value = "TP2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    act(() => {
      (container.querySelector("button") as HTMLButtonElement).click();
    });

    expect(container.querySelector("input")).toBeNull();
    expect(onClassification).toHaveBeenCalledWith(3, "TP2", null);
  });

  it("shows each configured title while keeping its canonical page type", () => {
    render(baseDecision, [
      { title: "TESTING", page_type: "TESTING" },
      { title: "TESTS", page_type: "TESTING" },
    ]);

    const options = [
      ...container.querySelectorAll<HTMLOptionElement>(
        'optgroup[label="preparationUi.classification.configuredTitles"] option',
      ),
    ];
    expect(options.map((option) => option.textContent)).toEqual(["TESTING", "TESTS"]);
    expect(options.map((option) => option.value)).toEqual([
      "TESTING",
      "configured-title:TESTS",
    ]);

    const select = container.querySelector("select") as HTMLSelectElement;
    act(() => {
      select.value = "configured-title:TESTS";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    act(() => {
      (container.querySelector("button") as HTMLButtonElement).click();
    });

    expect(onClassification).toHaveBeenCalledWith(3, "TESTING", "TESTS");
  });

  it("keeps a manually selected alias as the displayed title", () => {
    render(
      {
        ...baseDecision,
        page_type: "TESTING",
        page_title: "TESTS",
        page_type_source: "manual",
      },
      [
        { title: "TESTING", page_type: "TESTING" },
        { title: "TESTS", page_type: "TESTING" },
      ],
    );

    expect(container.querySelector(".prep-type-name")?.textContent).toBe("TESTS");
    expect((container.querySelector("select") as HTMLSelectElement).value).toBe(
      "configured-title:TESTS",
    );
    expect((container.querySelector("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows a manual source and detection evidence without a document-page number", () => {
    render({
      ...baseDecision,
      page_type: "TP1",
      page_type_source: "manual",
      classification_evidence: { footer_lines: ["JUL 27/26"], footer_page_key: "Page 401" },
    });

    expect(container.textContent).toContain("preparationUi.classification.source.manual");
    expect(container.textContent).toContain("JUL 27/26");
    expect(container.textContent).not.toContain("preparationUi.classification.documentPage");
    expect((container.querySelector("select") as HTMLSelectElement).value).toBe("TP1");
  });
});
