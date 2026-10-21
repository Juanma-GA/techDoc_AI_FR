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
    schema_version: 2,
    reference_index: 0,
    documents: [
      { index: 0, filename: "reference.pdf", page_count: 2 },
      { index: 1, filename: "revision-a.pdf", page_count: 3 },
      { index: 2, filename: "revision-b.pdf", page_count: 4 },
    ],
    page_slots: [
      { id: "reference-1", reference_page: 1 },
      { id: "reference-2", reference_page: 2 },
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
          { slot_id: "reference-2", reference_page: 2, comparison_page: 3, status: "aligned" },
        ],
      },
      {
        document_index: 2,
        filename: "revision-b.pdf",
        added_count: 1,
        removed_count: 0,
        changes: [
          { group_id: "doc-2-change-0", kind: "added", page: 1, text: "Additional clause", bbox: bbox(120) },
        ],
        page_alignment: [
          { slot_id: "reference-1", reference_page: 1, comparison_page: 2, status: "aligned" },
          { slot_id: "reference-2", reference_page: 2, comparison_page: 4, status: "changed" },
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

  it("links selected boxes and keeps the aligned page slot when switching PDFs", async () => {
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
    expect(container.querySelector('img[src$="/documents/1/pages/3.png"]')).not.toBeNull();

    const candidateSelect = container.querySelector<HTMLSelectElement>("#comparison-candidate");
    if (!candidateSelect) throw new Error("Expected the compared PDF selector.");
    await act(async () => {
      candidateSelect.value = "1";
      candidateSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(container.querySelector(".comparison-switcher__layer--outgoing")).not.toBeNull();
    expect(container.querySelector(".comparison-switcher__layer--incoming img[src$='/documents/2/pages/4.png']"))
      .not.toBeNull();
    expect(onSelectDifference).toHaveBeenLastCalledWith(null);
  });
});
