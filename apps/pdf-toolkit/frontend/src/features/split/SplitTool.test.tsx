// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import fr from "./locales/fr.json";
import en from "./locales/en.json";
import { SplitTool } from "./SplitTool";

const mocks = vi.hoisted(() => ({
  getDocument: vi.fn(),
  chooseDestination: vi.fn(),
  processSplit: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: mocks.getDocument,
}));
vi.mock("./AdvancedSplit", () => ({ AdvancedSplit: () => null }));
vi.mock("../../shared/components/FileDropzone", () => ({
  FileDropzone: ({ onFiles }: { onFiles: (files: File[]) => void }) => (
    <button type="button" onClick={() => {
      const file = new File(["synthetic PDF"], "manual.pdf", { type: "application/pdf" });
      Object.defineProperty(file, "arrayBuffer", { value: async () => new ArrayBuffer(8) });
      onFiles([file]);
    }}>Load synthetic PDF</button>
  ),
}));
vi.mock("../../shared/api", () => ({
  chooseSplitDestination: mocks.chooseDestination,
  processSplit: mocks.processSplit,
  validateExportFileName: () => null,
  formatOperationError: () => "Export failed",
}));

function node(title: string, page: number, items: ReturnType<typeof leaf>[] = []) {
  return { ...leaf(title, page), items };
}
function leaf(title: string, page: number) {
  return { title, dest: [page - 1], items: [] };
}
function mockPdf(outline: ReturnType<typeof node>[] | null = [
  node("A/B", 3, [leaf("Detail", 4)]), node("A:B", 7),
]) {
  const getOutline = vi.fn().mockResolvedValue(outline);
  const destroy = vi.fn().mockResolvedValue(undefined);
  mocks.getDocument.mockReturnValue({
    promise: Promise.resolve({ numPages: 8, getOutline }), destroy,
  });
  return { getOutline, destroy };
}

async function setup(language = "fr") {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: {
    fr: { translation: fr }, en: { translation: en },
  }, interpolation: { escapeValue: false } });
  render(<I18nextProvider i18n={i18n}><SplitTool /></I18nextProvider>);
  return {
    mode: language === "fr" ? "Mode de découpage" : "Split mode",
    action: language === "fr" ? "Découper et télécharger" : "Split and download",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue({});
  mocks.processSplit.mockResolvedValue("manual.zip");
  mockPdf();
});
afterEach(cleanup);

describe("SplitTool bookmark export", () => {
  it.each(["fr", "en"])("exports sanitized bookmark titles and leading pages (%s)", async (language) => {
    const labels = await setup(language);
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText(labels.mode), { target: { value: "bookmarks" } });
    const action = screen.getByRole("button", { name: labels.action }) as HTMLButtonElement;
    await waitFor(() => expect(action.disabled).toBe(false));
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processSplit).toHaveBeenCalledOnce());
    const data = mocks.processSplit.mock.calls[0]?.[0] as FormData;
    expect(JSON.parse(String(data.get("groups")))).toEqual([
      { name: "manual_01.pdf", pages: "1-2" },
      { name: "A_B.pdf", pages: "3-6" },
      { name: "A_B_2.pdf", pages: "7-8" },
    ]);
    expect(data.get("folder")).toBe("manual");
    expect(mocks.chooseDestination).toHaveBeenCalledWith("manual.zip", expect.any(Function));
  });

  it("selects a nested level", async () => {
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "bookmarks" } });
    const level = screen.getByLabelText("Niveau des signets") as HTMLSelectElement;
    await waitFor(() => expect(level.disabled).toBe(false));
    fireEvent.change(level, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Découper et télécharger" }));
    await waitFor(() => expect(mocks.processSplit).toHaveBeenCalledOnce());
    const data = mocks.processSplit.mock.calls[0]?.[0] as FormData;
    expect(JSON.parse(String(data.get("groups")))).toEqual([
      { name: "manual_01.pdf", pages: "1-3" }, { name: "Detail.pdf", pages: "4-8" },
    ]);
  });

  it("falls back to the first usable level when top-level bookmarks have no destination", async () => {
    mockPdf([node("Container", 0, [leaf("Nested", 1)])]);
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "bookmarks" } });
    const level = screen.getByLabelText("Niveau des signets") as HTMLSelectElement;
    await waitFor(() => expect(level.value).toBe("2"));
    fireEvent.click(screen.getByRole("button", { name: "Découper et télécharger" }));
    await waitFor(() => expect(mocks.processSplit).toHaveBeenCalledOnce());
    const data = mocks.processSplit.mock.calls[0]?.[0] as FormData;
    expect(JSON.parse(String(data.get("groups")))).toEqual([{ name: "Nested.pdf", pages: "1-8" }]);
  });

  it("shows an empty state and never reuses bookmarks from a previous file", async () => {
    const pdf = mockPdf();
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "bookmarks" } });
    const action = screen.getByRole("button", { name: "Découper et télécharger" }) as HTMLButtonElement;
    await waitFor(() => expect(action.disabled).toBe(false));
    mockPdf(null);
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    expect(action.disabled).toBe(true);
    await screen.findByText(fr.split.bookmarksEmpty);
    expect(action.disabled).toBe(true);
    expect(pdf.destroy).toHaveBeenCalledOnce();
    expect(mocks.processSplit).not.toHaveBeenCalled();
  });

  it("reports outline failures without breaking existing range and chunk exports", async () => {
    const pdf = mockPdf();
    pdf.getOutline.mockRejectedValue(new Error("Invalid outline"));
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "bookmarks" } });
    await screen.findByText(fr.split.bookmarksFailed);
    const action = screen.getByRole("button", { name: "Découper et télécharger" }) as HTMLButtonElement;
    expect(action.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "ranges" } });
    fireEvent.change(screen.getByLabelText("Plages personnalisées"), { target: { value: "1-2;3-8" } });
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processSplit).toHaveBeenCalledTimes(1));
    let data = mocks.processSplit.mock.calls[0]?.[0] as FormData;
    expect(JSON.parse(String(data.get("groups")))).toEqual([
      { name: "manual_01.pdf", pages: "1-2" }, { name: "manual_02.pdf", pages: "3-8" },
    ]);
    await waitFor(() => expect(action.disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "chunks" } });
    fireEvent.change(screen.getByLabelText("Un document toutes les N pages"), { target: { value: "4" } });
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processSplit).toHaveBeenCalledTimes(2));
    data = mocks.processSplit.mock.calls[1]?.[0] as FormData;
    expect(JSON.parse(String(data.get("groups")))).toEqual([
      { name: "manual_01.pdf", pages: "1-4" }, { name: "manual_02.pdf", pages: "5-8" },
    ]);
  });

  it("reports a PDF loading failure and disables export", async () => {
    mocks.getDocument.mockImplementation(() => ({
      promise: Promise.reject(new Error("Invalid PDF")),
      destroy: vi.fn().mockResolvedValue(undefined),
    }));
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    await screen.findByText(fr.split.documentFailed);
    const action = screen.getByRole("button", { name: "Découper et télécharger" }) as HTMLButtonElement;
    expect(action.disabled).toBe(true);
    expect(mocks.processSplit).not.toHaveBeenCalled();
  });

  it("shows loading state, warns about unusable bookmarks, and blocks over 5000 documents", async () => {
    const pdf = mockPdf();
    let finish!: (value: ReturnType<typeof node>[]) => void;
    pdf.getOutline.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    await setup();
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    fireEvent.change(screen.getByLabelText("Mode de découpage"), { target: { value: "bookmarks" } });
    await screen.findByText(fr.split.bookmarksLoading);
    const action = screen.getByRole("button", { name: "Découper et télécharger" }) as HTMLButtonElement;
    expect(action.disabled).toBe(true);
    await waitFor(() => expect(pdf.getOutline).toHaveBeenCalledOnce());
    finish([node("Valid", 1), node("Outside", 9)]);
    await screen.findByText("1 signet(s) ignoré(s) : aucune destination utilisable dans ce PDF.");
    expect(action.disabled).toBe(false);
    const largePdf = {
      numPages: 5000,
      getOutline: async () => Array.from({ length: 5000 }, (_, index) => node(`Part ${index}`, index + 1)),
    };
    mocks.getDocument.mockReturnValue({
      promise: Promise.resolve(largePdf),
      destroy: vi.fn().mockResolvedValue(undefined),
    });
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    await waitFor(() => expect(action.disabled).toBe(false));
    expect(screen.getByText("5000 PDF dans le dossier manual")).toBeTruthy();
    mocks.getDocument.mockReturnValue({
      promise: Promise.resolve({
        numPages: 5001,
        getOutline: async () => Array.from({ length: 5001 }, (_, index) => node(`Part ${index}`, index + 1)),
      }),
      destroy: vi.fn().mockResolvedValue(undefined),
    });
    fireEvent.click(screen.getByText("Load synthetic PDF"));
    await screen.findByText("Le découpage est limité à 5000 documents.");
    expect(action.disabled).toBe(true);
  });
});
