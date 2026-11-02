// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
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
  it("offers only the detected DM titles and retains manual page selection", async () => {
    const detection: PdfCutDetection = {
      validation_required: true,
      selected_page: null,
      selected_end_page: null,
      default_start_page: 2,
      total_pages: 10,
      dmrl_titles: ["Hydraulic system", "Pump assembly"],
      candidates: [],
    };
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { value: true, configurable: true });
    const onTitleChange = vi.fn();
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    try {
      await act(async () => root.render(createElement(PdfCutStartSelector, {
        docId: "doc-id",
        detection,
        selectedTitle: "Hydraulic system",
        startPage: 2,
        endPage: 10,
        busy: false,
        onTitleChange,
        onDetect: vi.fn(),
        onStartPageChange: vi.fn(),
        onEndPageChange: vi.fn(),
        onConfirm: vi.fn(),
      })));

      expect(container.textContent).toContain("Hydraulic system");
      expect(container.querySelector<HTMLInputElement>('input[name="startPage"]')?.value).toBe("2");
      expect(container.textContent).toContain("migration.upload.pdfCut.detectWithTitle");
      await act(async () => {
        container.querySelector<HTMLButtonElement>('button[aria-haspopup="listbox"]')?.click();
      });
      expect([...document.body.querySelectorAll('[role="option"]')]
        .map((option) => option.textContent?.trim())).toEqual(["Hydraulic system", "Pump assembly"]);
      await act(async () => {
        [...document.body.querySelectorAll<HTMLButtonElement>('[role="option"]')]
          .find((option) => option.textContent?.trim() === "Pump assembly")?.click();
      });
      expect(onTitleChange).toHaveBeenCalledWith("Pump assembly");
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });
});
