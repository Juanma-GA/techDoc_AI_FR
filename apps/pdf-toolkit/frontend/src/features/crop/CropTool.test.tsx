// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import en from "../../locales/en.json";
import fr from "../../locales/fr.json";
import cropEn from "./locales/en.json";
import cropFr from "./locales/fr.json";
import { CropTool } from "./CropTool";

const mocks = vi.hoisted(() => ({
  buildRectangles: vi.fn(),
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
  useCropPdf: vi.fn(),
}));

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
    reason instanceof Error ? reason.message : "Crop failed",
  processPDF: mocks.processPDF,
  validateExportFileName: () => null,
}));
vi.mock("./cropGeometry", () => ({
  buildPageCropRectangles: mocks.buildRectangles,
}));
vi.mock("./useCropPdf", () => ({ useCropPdf: mocks.useCropPdf }));

function mockPreviewWithStatus(status: "loading" | "ready") {
  mocks.useCropPdf.mockImplementation((file: File | null) => ({
    canvasRef: { current: null },
    documentProxy: file ? { numPages: 2 } : null,
    pageSize: { width: 612, height: 792 },
    status: file ? status : "empty",
  }));
}

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  const base = language === "fr" ? fr : en;
  const feature = language === "fr" ? cropFr : cropEn;
  await i18n.init({
    lng: language,
    resources: {
      [language]: {
        translation: {
          ...base,
          tools: { ...base.tools, ...feature.tools },
          crop: feature.crop,
        },
      },
    },
    interpolation: { escapeValue: false },
  });
  const { container } = render(
    <I18nextProvider i18n={i18n}>
      <CropTool />
    </I18nextProvider>,
  );
  fireEvent.click(screen.getByText("Select a PDF"));
  return {
    action: screen.getByRole("button", {
      name: language === "fr" ? "Recadrer et télécharger" : "Crop and download",
    }),
    container,
    language,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.buildRectangles.mockResolvedValue({
    rectangles: [
      { page: 1, x1: 10, y1: 10, x2: 500, y2: 700 },
      { page: 2, x1: 10, y1: 10, x2: 500, y2: 700 },
    ],
    changedPages: 2,
  });
  mocks.processPDF.mockResolvedValue("cropped.pdf");
  mockPreviewWithStatus("ready");
});

afterEach(cleanup);

describe("CropTool", () => {
  it("mounts the preview canvas while the first page is rendering", async () => {
    mockPreviewWithStatus("loading");
    const form = await setup();

    expect(form.container.querySelector(".crop-preview-page canvas")).not.toBeNull();
    expect(form.action.getAttribute("disabled")).not.toBeNull();
  });

  it("submits a manual crop for every page", async () => {
    const form = await setup();
    fireEvent.change(screen.getByLabelText("Gauche (%)"), { target: { value: "10" } });
    fireEvent.click(form.action);

    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const call = mocks.processPDF.mock.calls[0];
    const data = call?.[1];
    expect(call?.[0]).toBe("crop");
    expect(data).toBeInstanceOf(FormData);
    expect(mocks.buildRectangles).toHaveBeenCalledWith(
      expect.objectContaining({ numPages: 2 }),
      "manual",
      expect.objectContaining({ left: 0.1 }),
      expect.any(AbortSignal),
      expect.any(Function),
    );
    expect(JSON.parse(String(data?.get("crops")))).toHaveLength(2);
  });

  it("reports when automatic detection finds no margins", async () => {
    const form = await setup("en");
    mocks.buildRectangles.mockResolvedValue({ rectangles: [], changedPages: 0 });
    fireEvent.change(screen.getByLabelText("Cropping mode"), {
      target: { value: "automatic" },
    });
    fireEvent.click(form.action);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "No removable margins were detected.",
    );
    expect(mocks.processPDF).not.toHaveBeenCalled();
  });
});
