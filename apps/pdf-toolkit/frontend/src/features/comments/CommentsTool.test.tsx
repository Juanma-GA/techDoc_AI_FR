// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createInstance } from "i18next";
import { I18nextProvider } from "react-i18next";

import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import { CommentsTool } from "./CommentsTool";

const mocks = vi.hoisted(() => ({
  getDocument: vi.fn(),
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: mocks.getDocument,
}));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "worker.js" }));
vi.mock("../../shared/components/FileDropzone", () => ({
  FileDropzone: ({ onFiles }: { onFiles: (files: File[]) => void }) => (
    <button type="button" onClick={() => {
      const file = new File(["%PDF-synthetic"], "sample.pdf", { type: "application/pdf" });
      Object.defineProperty(file, "arrayBuffer", {
        value: () => Promise.resolve(new ArrayBuffer(1)),
      });
      onFiles([file]);
    }}>Select PDF</button>
  ),
}));
vi.mock("../../shared/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../shared/api")>();
  return {
    ...original,
    chooseExportDestination: mocks.chooseDestination,
    processPDF: mocks.processPDF,
  };
});

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  await i18n.init({
    lng: language,
    resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  render(<I18nextProvider i18n={i18n}><CommentsTool /></I18nextProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.processPDF.mockResolvedValue("commented.pdf");
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as CanvasRenderingContext2D);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0, y: 0, left: 0, top: 0, right: 600, bottom: 800, width: 600, height: 800,
    toJSON: () => ({}),
  } as DOMRect);
  const page = {
    getViewport: ({ scale = 1 }: { scale?: number }) => ({
      width: 600 * scale,
      height: 800 * scale,
      convertToPdfPoint: (x: number, y: number) => [x / scale, 800 - y / scale],
    }),
    render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    cleanup: vi.fn(),
  };
  mocks.getDocument.mockReturnValue({
    promise: Promise.resolve({
      numPages: 2,
      getPage: vi.fn().mockResolvedValue(page),
      destroy: vi.fn().mockResolvedValue(undefined),
    }),
    destroy: vi.fn().mockResolvedValue(undefined),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CommentsTool", () => {
  it("places a note by click and exports a PDF annotation", async () => {
    await setup();
    const exportButton = screen.getByRole("button", { name: "Enregistrer le PDF commenté" });
    expect((exportButton as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByText("Select PDF"));
    const preview = await screen.findByLabelText("Aperçu de la page 1 ; cliquez pour ajouter un commentaire.");
    const centerButton = screen.getByRole("button", { name: "Placer au centre" });
    await waitFor(() => expect((centerButton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(preview, { clientX: 150, clientY: 200 });

    const commentInput = screen.getByLabelText("Commentaire sur la page 1");
    fireEvent.change(commentInput, { target: { value: "À vérifier ici" } });
    fireEvent.click(screen.getByRole("button", { name: "Ajouter le commentaire" }));
    expect(screen.getByRole("button", { name: /Page 1.*À vérifier ici/ })).toBeTruthy();

    fireEvent.click(exportButton);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, name] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("comments");
    expect(name).toBe("commented.pdf");
    expect((data.get("file") as File).name).toBe("sample.pdf");
    expect(JSON.parse(data.get("comments") as string)).toEqual([
      { page: 1, x: 150, y: 600, content: "À vérifier ici" },
    ]);
    expect((await screen.findByRole("status")).textContent).toContain(
      "Le fichier commented.pdf a été téléchargé avec ses commentaires.",
    );
  });

  it("supports English and removing a placed comment", async () => {
    await setup("en");
    fireEvent.click(screen.getByText("Select PDF"));
    const preview = await screen.findByLabelText("Preview of page 1; click to add a comment.");
    fireEvent.click(preview, { clientX: 300, clientY: 400 });
    fireEvent.change(screen.getByLabelText("Comment on page 1"), {
      target: { value: "Review this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));
    expect(screen.getByRole("button", { name: /Page 1.*Review this/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove comment on page 1" }));
    expect(screen.getByText("No comments yet. Click the preview to add one.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save commented PDF" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
