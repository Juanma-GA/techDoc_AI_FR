import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { PdfCutDetection } from "../lib/api";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${Object.values(options).join(",")}` : key,
  }),
}));

import { PdfCutStartSelector } from "./PdfCutStartSelector";

describe("PDF start selector", () => {
  it("offers only the detected DM titles and retains manual page selection", () => {
    const detection: PdfCutDetection = {
      validation_required: true,
      selected_page: null,
      selected_end_page: null,
      default_start_page: 2,
      total_pages: 10,
      dmrl_titles: ["Hydraulic system", "Pump assembly"],
      candidates: [],
    };
    const markup = renderToStaticMarkup(
      createElement(PdfCutStartSelector, {
        docId: "doc-id",
        detection,
        selectedTitle: "Hydraulic system",
        startPage: 2,
        endPage: 10,
        busy: false,
        onTitleChange: vi.fn(),
        onDetect: vi.fn(),
        onStartPageChange: vi.fn(),
        onEndPageChange: vi.fn(),
        onConfirm: vi.fn(),
      }),
    );

    expect(markup).toContain("Hydraulic system");
    expect(markup).toContain("Pump assembly");
    expect(markup).toContain('value="2"');
    expect(markup).toContain("migration.upload.pdfCut.detectWithTitle");
  });
});
