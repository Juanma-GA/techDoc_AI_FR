// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import fr from "../../locales/fr.json";
import en from "../../locales/en.json";
import insertFr from "./locales/fr.json";
import insertEn from "./locales/en.json";
import { InsertTool } from "./InsertTool";

const mocks = vi.hoisted(() => ({
  getDocument: vi.fn(),
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: mocks.getDocument,
}));
vi.mock("../../shared/components/FileDropzone", () => ({
  FileDropzone: ({ label, onFiles }: { label: string; onFiles: (files: File[]) => void }) => (
    <button type="button" onClick={() => {
      const pages = label.includes("source") ? 5 : 3;
      const file = new File(["synthetic PDF"], `${pages}-pages.pdf`, { type: "application/pdf" });
      Object.defineProperty(file, "arrayBuffer", { value: async () => new ArrayBuffer(pages) });
      onFiles([file]);
    }}>{label}</button>
  ),
}));
vi.mock("../../shared/api", () => ({
  chooseExportDestination: mocks.chooseDestination,
  processPDF: mocks.processPDF,
  validateExportFileName: () => null,
  formatOperationError: () => "Export failed",
}));

const labels = {
  fr: {
    target: "Déposer le PDF de destination", source: "Déposer le PDF source",
    pages: "Pages de A à insérer", position: "Position dans B",
    afterPage: "Après la page de B", action: "Insérer et télécharger",
  },
  en: {
    target: "Drop the target PDF", source: "Drop the source PDF",
    pages: "Pages of A to insert", position: "Position in B",
    afterPage: "After page of B", action: "Insert and download",
  },
};

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: {
    fr: { translation: { ...fr, tools: { ...fr.tools, ...insertFr.tools }, insert: insertFr.insert } },
    en: { translation: { ...en, tools: { ...en.tools, ...insertEn.tools }, insert: insertEn.insert } },
  }, interpolation: { escapeValue: false } });
  render(<I18nextProvider i18n={i18n}><InsertTool /></I18nextProvider>);
  const text = labels[language];
  fireEvent.click(screen.getByText(text.target));
  fireEvent.click(screen.getByText(text.source));
  const action = screen.getByRole("button", { name: text.action }) as HTMLButtonElement;
  await waitFor(() => expect(action.disabled).toBe(false));
  return { text, action };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue({});
  mocks.processPDF.mockResolvedValue("inserted.pdf");
  mocks.getDocument.mockImplementation(({ data }: { data: Uint8Array }) => ({
    promise: Promise.resolve({ numPages: data.length }),
    destroy: vi.fn().mockResolvedValue(undefined),
  }));
});
afterEach(cleanup);

describe("InsertTool", () => {
  it.each(["fr", "en"] as const)("sends target, source, typed pages and position (%s)", async (language) => {
    const { text, action } = await setup(language);
    fireEvent.change(screen.getByLabelText(text.pages), { target: { value: "5,1-3" } });
    fireEvent.change(screen.getByLabelText(text.position), { target: { value: "after" } });
    fireEvent.change(screen.getByLabelText(text.afterPage), { target: { value: "2" } });
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, name] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("insert");
    expect(name).toBe("inserted.pdf");
    expect((data.getAll("files") as File[]).map((file) => file.name)).toEqual([
      "3-pages.pdf", "5-pages.pdf",
    ]);
    expect(data.get("pages")).toBe("5,1-3");
    expect(data.get("after")).toBe("2");
  });

  it("inserts every source page at the end by default", async () => {
    const { action } = await setup();
    expect(screen.getByText("5 pages insérées après la page 3 de B.")).toBeTruthy();
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const data = mocks.processPDF.mock.calls[0]?.[1] as FormData;
    expect(data.get("pages")).toBe("");
    expect(data.get("after")).toBe("3");
  });

  it("maps the start position to zero", async () => {
    const { text, action } = await setup();
    fireEvent.change(screen.getByLabelText(text.position), { target: { value: "start" } });
    expect(screen.getByText("5 pages insérées au début de B.")).toBeTruthy();
    fireEvent.click(action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    expect((mocks.processPDF.mock.calls[0]?.[1] as FormData).get("after")).toBe("0");
  });

  it("blocks invalid pages and positions", async () => {
    const { text, action } = await setup();
    fireEvent.change(screen.getByLabelText(text.pages), { target: { value: "6" } });
    expect(action.disabled).toBe(true);
    expect(screen.getByText(/Sélection invalide/u)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(text.pages), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(text.position), { target: { value: "after" } });
    fireEvent.change(screen.getByLabelText(text.afterPage), { target: { value: "4" } });
    expect(action.disabled).toBe(true);
    expect(screen.getByText("Position invalide pour le PDF de destination.")).toBeTruthy();
    expect(mocks.processPDF).not.toHaveBeenCalled();
  });
});
