import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ComparisonDetail } from "../../lib/comparisonApi";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, string | number>) =>
      values ? `${key} ${JSON.stringify(values)}` : key,
  }),
}));

import { ComparisonWorkspace } from "./ComparisonWorkspace";

const bbox = (x0: number) => ({
  x0,
  y0: 70,
  x1: x0 + 80,
  y1: 90,
  page_w: 500,
  page_h: 700,
  page_rotation: 0,
});

const comparison: ComparisonDetail = {
  id: "comparison-id",
  title: "reference.pdf",
  created_at: "2026-01-01T00:00:00Z",
  file_count: 3,
  ai_status: "pending",
  ai_summary: null,
  ai_summary_truncated: false,
  report: {
    schema_version: 5,
    reference_index: 0,
    documents: [
      { index: 0, filename: "reference.pdf", page_count: 10 },
      { index: 1, filename: "revision-a.pdf", page_count: 9 },
      { index: 2, filename: "revision-b.pdf", page_count: 4 },
    ],
    page_slots: [
      { id: "reference-1", reference_page: 1 },
      { id: "comparison-1-page-2", reference_page: null },
      { id: "comparison-1-page-3", reference_page: null },
      { id: "comparison-2-page-1", reference_page: null },
      { id: "reference-2", reference_page: 2 },
      { id: "comparison-2-page-3", reference_page: null },
      { id: "reference-3", reference_page: 3 },
      { id: "reference-4", reference_page: 4 },
      { id: "reference-5", reference_page: 5 },
      { id: "reference-6", reference_page: 6 },
      { id: "reference-7", reference_page: 7 },
      { id: "reference-8", reference_page: 8 },
      { id: "reference-9", reference_page: 9 },
      { id: "reference-10", reference_page: 10 },
    ],
    comparisons: [
      {
        document_index: 1,
        filename: "revision-a.pdf",
        added_count: 1,
        removed_count: 1,
        changes: [
          { group_id: "doc-1-change-0", kind: "removed", page: 1, text: "Old clause", bbox: bbox(50) },
          { group_id: "doc-1-change-0", kind: "added", page: 1, text: "New clause", bbox: bbox(160) },
        ],
        page_alignment: [
          { slot_id: "reference-1", reference_page: 1, comparison_page: 1, status: "changed" },
          { slot_id: "comparison-1-page-2", reference_page: null, comparison_page: 2, status: "comparison_only" },
          { slot_id: "comparison-1-page-3", reference_page: null, comparison_page: 3, status: "comparison_only" },
          { slot_id: "reference-2", reference_page: 2, comparison_page: 4, status: "aligned" },
          { slot_id: "reference-3", reference_page: 3, comparison_page: 5, status: "aligned" },
          { slot_id: "reference-4", reference_page: 4, comparison_page: 6, status: "aligned" },
          { slot_id: "reference-5", reference_page: 5, comparison_page: 7, status: "aligned" },
          { slot_id: "reference-6", reference_page: 6, comparison_page: 8, status: "aligned" },
          { slot_id: "reference-7", reference_page: 7, comparison_page: 9, status: "aligned" },
          { slot_id: "reference-8", reference_page: 8, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-9", reference_page: 9, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-10", reference_page: 10, comparison_page: null, status: "reference_only" },
        ],
      },
      {
        document_index: 2,
        filename: "revision-b.pdf",
        added_count: 1,
        removed_count: 0,
        changes: [
          { group_id: "doc-2-change-0", kind: "added", page: 4, text: "Additional clause", bbox: bbox(120) },
        ],
        page_alignment: [
          { slot_id: "comparison-2-page-1", reference_page: null, comparison_page: 1, status: "comparison_only" },
          { slot_id: "reference-1", reference_page: 1, comparison_page: 2, status: "aligned" },
          { slot_id: "comparison-2-page-3", reference_page: null, comparison_page: 3, status: "comparison_only" },
          { slot_id: "reference-2", reference_page: 2, comparison_page: 4, status: "changed" },
          { slot_id: "reference-3", reference_page: 3, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-4", reference_page: 4, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-5", reference_page: 5, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-6", reference_page: 6, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-7", reference_page: 7, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-8", reference_page: 8, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-9", reference_page: 9, comparison_page: null, status: "reference_only" },
          { slot_id: "reference-10", reference_page: 10, comparison_page: null, status: "reference_only" },
        ],
      },
    ],
  },
};

describe("ComparisonWorkspace", () => {
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
  });

  it("skips unmatched pages and shows the matched page numbers when switching PDFs", async () => {
    const onSelectDifference = vi.fn();
    await act(async () => {
      root.render(
        <ComparisonWorkspace
          comparison={comparison}
          language="fr"
          onSelectDifference={onSelectDifference}
        />,
      );
    });

    const boxes = container.querySelectorAll<HTMLButtonElement>(".comparison-diff-box");
    expect(boxes).toHaveLength(2);
    await act(async () => boxes[0]?.click());
    expect(container.querySelectorAll(".comparison-diff-box.is-selected")).toHaveLength(2);
    expect(onSelectDifference).toHaveBeenLastCalledWith({
      documentIndex: 1,
      groupId: "doc-1-change-0",
    });

    const nextPage = container.querySelector<HTMLButtonElement>(
      'button[aria-label="comparison.nextPage"]',
    );
    await act(async () => nextPage?.click());
    expect(container.querySelector('img[src$="/documents/0/pages/2.png"]')).not.toBeNull();
    expect(container.querySelector('img[src$="/documents/1/pages/4.png"]')).not.toBeNull();
    expect(container.querySelector('img[src$="/documents/0/pages/8.png"]')).toBeNull();
    expect(container.querySelector('img[src$="/documents/1/pages/2.png"]')).toBeNull();
    expect(container.querySelector('img[src$="/documents/1/pages/3.png"]')).toBeNull();
    expect(container.querySelector(".comparison-unmatched-pages-status")?.textContent).toContain(
      'comparison.referenceOnlyPages {"pages":"8, 9, 10"}',
    );
    expect(container.querySelector(".comparison-unmatched-pages-status")?.textContent).toContain(
      'comparison.comparisonOnlyPages {"pages":"2, 3"}',
    );
    expect(
      Array.from(
        container.querySelectorAll(".comparison-pane-header .label"),
        (label) => label.textContent,
      ),
    ).toEqual(['comparison.page {"page":2}', 'comparison.page {"page":4}']);
    expect(container.querySelector(".comparison-alignment-status")?.textContent).toContain(
      'comparison.pageNumbersDiffer {"reference":2,"comparison":4}',
    );

    for (let page = 0; page < 5; page += 1) {
      const nextMatchedPage = container.querySelector<HTMLButtonElement>(
        'button[aria-label="comparison.nextPage"]',
      );
      if (!nextMatchedPage) throw new Error("Expected the next matched page control.");
      await act(async () => nextMatchedPage.click());
    }
    expect(container.querySelector('img[src$="/documents/0/pages/7.png"]')).not.toBeNull();
    expect(container.querySelector('img[src$="/documents/1/pages/9.png"]')).not.toBeNull();
    expect(container.querySelector(".comparison-page-control span")?.textContent).toContain(
      'comparison.pagePosition {"current":7,"total":7}',
    );
    expect(container.querySelector(".comparison-alignment-status")?.textContent).toContain(
      'comparison.pageNumbersDiffer {"reference":7,"comparison":9}',
    );

    const candidateSelect = container.querySelector<HTMLSelectElement>("#comparison-candidate");
    if (!candidateSelect) throw new Error("Expected the compared PDF selector.");
    await act(async () => {
      candidateSelect.value = "1";
      candidateSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(container.querySelector(".comparison-switcher__layer--outgoing")).not.toBeNull();
    expect(container.querySelector(".comparison-switcher__layer--incoming img[src$='/documents/2/pages/2.png']"))
      .not.toBeNull();
    expect(container.querySelector(".comparison-unmatched-pages-status")?.textContent).toContain(
      'comparison.comparisonOnlyPages {"pages":"1, 3"}',
    );
    expect(onSelectDifference).toHaveBeenLastCalledWith(null);
  });
});
