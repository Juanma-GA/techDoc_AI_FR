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

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}

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
  vi.stubGlobal("PointerEvent", TestPointerEvent);
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
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CommentsTool", () => {
  it("draws a comment box and exports a PDF highlight", async () => {
    await setup();
    const exportButton = screen.getByRole("button", { name: "Enregistrer le PDF commenté" });
    expect((exportButton as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByText("Select PDF"));
    const preview = await screen.findByLabelText("Aperçu de la page 1 ; dessinez un cadre pour ajouter un commentaire.");
    const centerButton = screen.getByRole("button", { name: "Créer un cadre au centre" });
    await waitFor(() => expect((centerButton as HTMLButtonElement).disabled).toBe(false));
    const page = preview.parentElement as HTMLElement;
    expect(page.classList.contains("is-ready")).toBe(true);
    expect(page.classList.contains("is-drawable")).toBe(true);
    fireEvent.pointerDown(page, { pointerId: 1, button: 0, clientX: 60, clientY: 80 });
    fireEvent.pointerMove(page, { pointerId: 1, clientX: 240, clientY: 320 });
    fireEvent.pointerUp(page, { pointerId: 1, clientX: 240, clientY: 320 });

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
      { page: 1, x1: 60, y1: 720, x2: 240, y2: 480, content: "À vérifier ici" },
    ]);
    expect((await screen.findByRole("status")).textContent).toContain(
      "Le fichier commented.pdf a été téléchargé avec ses commentaires.",
    );
  });

  it("supports English and removing a placed comment", async () => {
    await setup("en");
    fireEvent.click(screen.getByText("Select PDF"));
    const preview = await screen.findByLabelText("Preview of page 1; draw a box to add a comment.");
    const page = preview.parentElement as HTMLElement;
    fireEvent.pointerDown(page, { pointerId: 1, button: 0, clientX: 300, clientY: 400 });
    fireEvent.pointerUp(page, { pointerId: 1, clientX: 360, clientY: 460 });
    fireEvent.change(screen.getByLabelText("Comment on page 1"), {
      target: { value: "Review this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));
    expect(screen.getByRole("button", { name: /Page 1.*Review this/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove comment on page 1" }));
    expect(screen.getByText("No comments yet. Draw a box on the preview to add one.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save commented PDF" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("supports adjusting the box dimensions from the keyboard", async () => {
    await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    const centerButton = await screen.findByRole("button", { name: "Créer un cadre au centre" });
    await waitFor(() => expect((centerButton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(centerButton);
    fireEvent.change(screen.getByLabelText("Largeur (%)"), { target: { value: "30" } });
    expect((screen.getByLabelText("Largeur (%)") as HTMLInputElement).value).toBe("30");
  });
});
