import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../hooks/useDocuments", () => ({
  useDeleteDocument: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useDocuments: () => ({
    data: [
      {
        id: "document-1",
        working_format: "pdf",
        original_filename: "manual.pdf",
        page_count: 5,
      },
    ],
    isLoading: false,
    isError: false,
  }),
  useUploadDocument: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../stores/filtersStore", () => ({
  effectiveTarget: () => null,
  useFiltersStore: (selector: (state: { targetUnits: unknown[] }) => unknown) =>
    selector({ targetUnits: [] }),
}));

vi.mock("../components/DocumentDeleteButton", () => ({
  DocumentDeleteButton: () => <button type="button">delete</button>,
}));

vi.mock("../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../components/upload/PdfUploadZone", () => ({
  PdfUploadZone: () => null,
}));

import { Preparation } from "./Preparation";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Preparation", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("opens a saved preparation document from its card and keyboard focus", () => {
    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/preparation"]}>
          <Routes>
            <Route path="/preparation" element={<Preparation />} />
            <Route path="/preparation/:id" element={<p>preparation workspace</p>} />
          </Routes>
        </MemoryRouter>,
      );
    });

    const row = container.querySelector(".prep-document-row");
    expect(row?.getAttribute("role")).toBe("link");
    expect(row?.getAttribute("tabindex")).toBe("0");

    const deleteButton = row?.querySelectorAll("button")[1];
    act(() => deleteButton?.click());
    expect(container.textContent).not.toContain("preparation workspace");

    act(() => {
      row?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("preparation workspace");
  });

  it("opens a saved preparation document with Enter", () => {
    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/preparation"]}>
          <Routes>
            <Route path="/preparation" element={<Preparation />} />
            <Route path="/preparation/:id" element={<p>preparation workspace</p>} />
          </Routes>
        </MemoryRouter>,
      );
    });

    const row = container.querySelector(".prep-document-row");
    act(() => {
      row?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });

    expect(container.textContent).toContain("preparation workspace");
  });

  it("keeps the open button functional", () => {
    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/preparation"]}>
          <Routes>
            <Route path="/preparation" element={<Preparation />} />
            <Route path="/preparation/:id" element={<p>preparation workspace</p>} />
          </Routes>
        </MemoryRouter>,
      );
    });

    const openButton = container.querySelector<HTMLButtonElement>(
      ".prep-document-row .btn.primary",
    );
    act(() => openButton?.click());

    expect(container.textContent).toContain("preparation workspace");
  });
});
