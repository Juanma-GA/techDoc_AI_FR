// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import extractImagesEn from "./locales/en.json";
import extractImagesFr from "./locales/fr.json";
import { ExtractImagesTool } from "./ExtractImagesTool";

const mocks = vi.hoisted(() => ({
  chooseDestination: vi.fn(),
  checkReadablePdf: vi.fn(),
  extract: vi.fn(),
  saveBlob: vi.fn(),
  unpack: vi.fn(),
}));
const revokeObjectURL = vi.fn();
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: revokeObjectURL,
});

vi.mock("../../shared/components/FileDropzone", () => ({
  FileDropzone: ({ onFiles }: { onFiles: (files: File[]) => void }) => (
    <button
      type="button"
      onClick={() =>
        onFiles([new File(["%PDF-synthetic"], "sample.pdf", { type: "application/pdf" })])
      }
    >
      Select a PDF
    </button>
  ),
}));
vi.mock("../../shared/api", () => ({
  chooseExportDestination: mocks.chooseDestination,
  formatOperationError: (reason: unknown) =>
    reason instanceof Error ? reason.message : "Extraction failed",
  saveExportBlob: mocks.saveBlob,
  validateExportFileName: () => null,
}));
vi.mock("./extractImagesApi", () => ({
  extractImagesFromPDF: mocks.extract,
}));
vi.mock("./checkReadablePdf", () => ({
  checkReadablePdf: mocks.checkReadablePdf,
}));
vi.mock("./unpackImageArchive", async (importOriginal) => {
  const original = await importOriginal<typeof import("./unpackImageArchive")>();
  return { ...original, unpackImageArchive: mocks.unpack };
});

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  const base = language === "fr" ? fr : en;
  const feature = language === "fr" ? extractImagesFr : extractImagesEn;
  await i18n.init({
    lng: language,
    resources: {
      [language]: {
        translation: {
          ...base,
          tools: { ...base.tools, ...feature.tools },
          extractImages: feature.extractImages,
        },
      },
    },
    interpolation: { escapeValue: false },
  });
  render(
    <I18nextProvider i18n={i18n}>
      <ExtractImagesTool />
    </I18nextProvider>,
  );
  fireEvent.click(screen.getByText("Select a PDF"));
  return {
    action: screen.getByRole("button", {
      name:
        language === "fr"
          ? "Extraire et afficher les images"
          : "Extract and show images",
    }),
    language,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.checkReadablePdf.mockResolvedValue(undefined);
  mocks.extract.mockResolvedValue(new Blob(["zip"], { type: "application/zip" }));
  mocks.saveBlob.mockResolvedValue("extracted-images.zip");
  mocks.unpack.mockResolvedValue([
    {
      name: "page-0001-image-0001.png",
      url: "blob:preview-1",
      size: 4,
      previewable: true,
      contentHash: "png-hash",
    },
    {
      name: "page-0001-image-0002.jbig2",
      url: "blob:preview-2",
      size: 3,
      previewable: false,
      contentHash: "jbig2-hash",
    },
  ]);
});
afterEach(cleanup);

describe("ExtractImagesTool", () => {
  it.each(["fr", "en"] as const)("shows images before offering the ZIP download (%s)", async (language) => {
    const form = await setup(language);
    fireEvent.click(form.action);

    await screen.findByRole("heading", {
      name: language === "fr" ? "Vignettes des images (2)" : "Image previews (2)",
    });
    expect(mocks.extract).toHaveBeenCalledOnce();
    expect(mocks.unpack).toHaveBeenCalledOnce();
    expect(mocks.chooseDestination).not.toHaveBeenCalled();
    expect(mocks.saveBlob).not.toHaveBeenCalled();

    const imageDownload = screen.getByRole("link", {
      name:
        language === "fr"
          ? "Télécharger page-0001-image-0001.png"
          : "Download page-0001-image-0001.png",
    });
    expect(imageDownload.getAttribute("download")).toBe("page-0001-image-0001.png");
    expect(imageDownload.getAttribute("href")).toBe("blob:preview-1");
    expect(screen.getByRole("img", { name: "page-0001-image-0001.png" })).toBeTruthy();
    expect(screen.getByText(language === "fr" ? "Aperçu indisponible pour ce format" : "Preview unavailable for this format")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", {
        name: language === "fr" ? "Télécharger l’archive ZIP" : "Download ZIP archive",
      }),
    );
    await waitFor(() => expect(mocks.saveBlob).toHaveBeenCalledOnce());
    expect(mocks.chooseDestination).toHaveBeenCalledOnce();
  });

  it("reports extraction errors", async () => {
    const form = await setup();
    mocks.extract.mockRejectedValue(new Error("No embedded images"));
    fireEvent.click(form.action);

    expect((await screen.findByRole("alert")).textContent).toContain("No embedded images");
    expect(screen.queryByRole("button", { name: "Télécharger l’archive ZIP" })).toBeNull();
    expect(mocks.chooseDestination).not.toHaveBeenCalled();
    expect(mocks.saveBlob).not.toHaveBeenCalled();
  });

  it("groups identical images once and shows their occurrence count", async () => {
    const form = await setup();
    mocks.unpack.mockResolvedValue([
      {
        name: "page-0001-logo.png",
        url: "blob:logo-1",
        size: 4,
        previewable: true,
        contentHash: "same-logo",
      },
      {
        name: "page-0002-logo.png",
        url: "blob:logo-2",
        size: 4,
        previewable: true,
        contentHash: "same-logo",
      },
      {
        name: "page-0002-product.jpg",
        url: "blob:product",
        size: 8,
        previewable: true,
        contentHash: "unique-product",
      },
    ]);
    fireEvent.click(form.action);

    expect(await screen.findByText("2 occurrences identiques")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Éléments récurrents (logos/icônes)" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Images uniques" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Télécharger page-0001-logo.png" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Télécharger page-0002-logo.png" })).toBeNull();
    expect(screen.getByRole("link", { name: "Télécharger page-0002-product.jpg" })).toBeTruthy();
  });

  it.each([
    ["unreadablePdf", "Ce PDF est illisible, protégé ou invalide et ne peut pas être traité."],
    ["noTextLayer", "Aucun texte lisible n’a été détecté. Ce PDF semble être un scan sans OCR."],
  ] as const)("rejects unreadable PDFs before calling the backend (%s)", async (_case, message) => {
    const form = await setup();
    mocks.checkReadablePdf.mockRejectedValue(new Error(message));
    fireEvent.click(form.action);

    expect((await screen.findByRole("alert")).textContent).toBe(message);
    expect(mocks.extract).not.toHaveBeenCalled();
    expect(mocks.chooseDestination).not.toHaveBeenCalled();
    expect(mocks.saveBlob).not.toHaveBeenCalled();
  });
});
