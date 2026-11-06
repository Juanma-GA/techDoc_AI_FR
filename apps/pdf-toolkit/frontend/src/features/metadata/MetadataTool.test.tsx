// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createInstance } from "i18next";
import { I18nextProvider } from "react-i18next";

import fr from "../../locales/fr.json";
import en from "../../locales/en.json";
import { MetadataTool } from "./MetadataTool";

const mocks = vi.hoisted(() => ({
  getDocument: vi.fn(),
  getMetadata: vi.fn(),
  destroy: vi.fn(),
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: mocks.getDocument,
}));
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
  render(<I18nextProvider i18n={i18n}><MetadataTool /></I18nextProvider>);
  return {
    action: screen.getByRole("button", {
      name: language === "fr" ? "Enregistrer et télécharger" : "Save and download",
    }) as HTMLButtonElement,
    title: screen.getByLabelText(language === "fr" ? "Titre" : "Title") as HTMLInputElement,
    author: screen.getByLabelText(language === "fr" ? "Auteur" : "Author") as HTMLInputElement,
    subject: screen.getByLabelText(language === "fr" ? "Sujet" : "Subject") as HTMLInputElement,
    keywords: screen.getByLabelText(language === "fr" ? "Mots-clés" : "Keywords") as HTMLInputElement,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.processPDF.mockResolvedValue("metadata.pdf");
  mocks.destroy.mockResolvedValue(undefined);
  mocks.getMetadata.mockResolvedValue({
    info: { Title: "Existing title", Author: "Existing author", Subject: "Existing subject", Keywords: "one, two" },
    metadata: null,
  });
  mocks.getDocument.mockImplementation(() => ({
    promise: Promise.resolve({ getMetadata: mocks.getMetadata }),
    destroy: mocks.destroy,
  }));
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MetadataTool", () => {
  it.each(["fr", "en"] as const)("prefills, edits and clears properties (%s)", async (language) => {
    const form = await setup(language);
    expect(form.action.disabled).toBe(true);
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.title.value).toBe("Existing title"));
    expect(form.author.value).toBe("Existing author");
    expect(form.subject.value).toBe("Existing subject");
    expect(form.keywords.value).toBe("one, two");
    expect(form.action.disabled).toBe(false);
    fireEvent.change(form.title, { target: { value: "Nouveau titre" } });
    fireEvent.change(form.author, { target: { value: "Nouvel auteur" } });
    fireEvent.change(form.subject, { target: { value: "" } });
    fireEvent.change(form.keywords, { target: { value: "alpha; beta" } });
    fireEvent.click(form.action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, name] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("edit-metadata");
    expect(name).toBe("metadata.pdf");
    expect((data.get("file") as File).name).toBe("sample.pdf");
    expect(data.get("title")).toBe("Nouveau titre");
    expect(data.get("author")).toBe("Nouvel auteur");
    expect(data.get("subject")).toBe("");
    expect(data.get("keywords")).toBe("alpha; beta");
    expect((await screen.findByRole("status")).textContent).toContain("metadata.pdf");
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it("prefills missing Info values from XMP without replacing Info values", async () => {
    mocks.getMetadata.mockResolvedValue({
      info: { Title: "Info title" },
      metadata: { get: (key: string) => ({
        "dc:title": "XMP title", "dc:creator": ["Alice", "Bob"],
        "dc:description": "XMP subject", "dc:subject": ["tag1", "tag2"],
      })[key] },
    });
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.title.value).toBe("Info title"));
    expect(form.author.value).toBe("Alice, Bob");
    expect(form.subject.value).toBe("XMP subject");
    expect(form.keywords.value).toBe("tag1, tag2");
  });

  it("allows a PDF without any metadata", async () => {
    mocks.getMetadata.mockResolvedValue({ info: {}, metadata: null });
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.action.disabled).toBe(false));
    expect(form.title.value).toBe("");
    fireEvent.click(form.action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
  });

  it("reports read failure and blocks export instead of erasing properties", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.getMetadata.mockRejectedValue(new Error("invalid PDF"));
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    expect((await screen.findByRole("alert")).textContent).toContain("Impossible de lire");
    expect(form.action.disabled).toBe(true);
    expect(mocks.processPDF).not.toHaveBeenCalled();
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it("does not export after cancelling the save dialog", async () => {
    mocks.chooseDestination.mockResolvedValue(null);
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.action.disabled).toBe(false));
    fireEvent.click(form.action);
    await waitFor(() => expect(mocks.chooseDestination).toHaveBeenCalledOnce());
    expect(mocks.processPDF).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("reports export errors", async () => {
    mocks.processPDF.mockRejectedValue(new Error("Operation failed"));
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.action.disabled).toBe(false));
    fireEvent.click(form.action);
    expect((await screen.findByRole("alert")).textContent).toContain("Operation failed");
  });

  it("clears loaded properties when removing the file", async () => {
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.title.value).toBe("Existing title"));
    fireEvent.click(screen.getByRole("button", { name: "Retirer le fichier" }));
    await waitFor(() => expect(form.title.value).toBe(""));
    expect(form.action.disabled).toBe(true);
  });

  it("does not overwrite the current file with a stale metadata response", async () => {
    let resolveOld: (value: { info: { Title: string }; metadata: null }) => void = () => {
      throw new Error("The old read has not started");
    };
    const oldRead = new Promise<{ info: { Title: string }; metadata: null }>((resolve) => {
      resolveOld = resolve;
    });
    mocks.getMetadata.mockImplementationOnce(() => oldRead);
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(mocks.getMetadata).toHaveBeenCalledOnce());
    expect(form.action.disabled).toBe(true);

    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.title.value).toBe("Existing title"));
    resolveOld({ info: { Title: "Old file title" }, metadata: null });
    await waitFor(() => expect(mocks.destroy).toHaveBeenCalledTimes(2));
    expect(form.title.value).toBe("Existing title");
    expect(form.action.disabled).toBe(false);
  });

  it("rejects an invalid output filename before export", async () => {
    const form = await setup();
    fireEvent.click(screen.getByText("Select PDF"));
    await waitFor(() => expect(form.action.disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Nom du fichier de sortie"), {
      target: { value: "invalid/name.pdf" },
    });
    fireEvent.click(form.action);
    expect((await screen.findByRole("alert")).textContent).toContain("nom de fichier valide");
    expect(mocks.chooseDestination).not.toHaveBeenCalled();
    expect(mocks.processPDF).not.toHaveBeenCalled();
  });
});
