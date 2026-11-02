// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import fr from "../../locales/fr.json";
import en from "../../locales/en.json";
import { CleanTool } from "./CleanTool";

const mocks = vi.hoisted(() => ({
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
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
  processPDF: mocks.processPDF,
  validateExportFileName: () => null,
  formatOperationError: () => "Cleaning failed",
}));

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  await i18n.init({
    lng: language,
    resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  render(
    <I18nextProvider i18n={i18n}>
      <CleanTool />
    </I18nextProvider>,
  );
  fireEvent.click(screen.getByText("Select a PDF"));
  return {
    action: screen.getByRole("button", {
      name: language === "fr" ? "Nettoyer et télécharger" : "Clean and download",
    }),
    language,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.processPDF.mockResolvedValue("cleaned.pdf");
});
afterEach(cleanup);

describe("CleanTool", () => {
  it.each(["fr", "en"] as const)("removes PDF metadata and annotations (%s)", async (language) => {
    const form = await setup(language);
    expect(screen.getByText(language === "fr"
      ? "Les pièces jointes et scripts ne sont pas supprimés. Une signature numérique existante peut être invalidée."
      : "Attachments and scripts are not removed. An existing digital signature may be invalidated.")).toBeTruthy();

    fireEvent.click(form.action);
    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, filename] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("clean");
    expect(filename).toBe("cleaned.pdf");
    expect((data.get("file") as File).name).toBe("sample.pdf");
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("reports processing failures", async () => {
    const form = await setup();
    mocks.processPDF.mockRejectedValue(new Error("request failed"));
    fireEvent.click(form.action);

    expect((await screen.findByRole("alert")).textContent).toContain("Cleaning failed");
  });
});
