import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { Home } from "./Home";
import { mockWorkspaceApi, renderWorkflow as render, selectExcelPartInHome } from "../test/workflow";

const originalUrlMethodDescriptors = new Map(
  ["createObjectURL", "revokeObjectURL"].map((method) => [
    method,
    Object.getOwnPropertyDescriptor(URL, method),
  ]),
);

describe("Image Processor home workflow", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("fr");
    mockWorkspaceApi();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    for (const [method, descriptor] of originalUrlMethodDescriptors) {
      if (descriptor) {
        Object.defineProperty(URL, method, descriptor);
      } else {
        Reflect.deleteProperty(URL, method);
      }
    }
  });

  it("starts with OCR disabled until an image is selected", async () => {
    render(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");

    expect(screen.getByRole("heading", { name: "Détection et remplacement" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" })).toBeDisabled();
  });

  it("adds and removes manual replacement pairs accessibly", async () => {
    const user = userEvent.setup();
    render(<Home />);

    await user.click(screen.getByRole("button", { name: "Ajouter un couple" }));
    expect(screen.getByRole("textbox", { name: "Référence à remplacer 1" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nouveau repère 1" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Supprimer le couple 1" }));
    expect(screen.queryByRole("textbox", { name: "Référence à remplacer 1" })).not.toBeInTheDocument();
  });

  it("shows an empty state when the selected Excel part has no pairs", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);
    vi.spyOn(imageReplaceApi, "excelPairs").mockResolvedValue({ pairs: [] });

    await selectExcelPartInHome(user, container);

    expect(await screen.findByText("Aucun couple trouvé pour cette pièce.")).toBeInTheDocument();
  });

  it("shows a preview error instead of a false empty state", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);
    vi.spyOn(imageReplaceApi, "excelPairs").mockRejectedValue(new Error("Preview failed"));

    await selectExcelPartInHome(user, container);

    expect(await screen.findByRole("alert")).toHaveTextContent("Preview failed");
    expect(screen.queryByText("Aucun couple trouvé pour cette pièce.")).not.toBeInTheDocument();
  });

  it("loads, edits, removes, and submits Excel replacement pairs", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);
    const imageInput = container.querySelector<HTMLInputElement>(
      'input[type="file"][accept^="image/"]',
    );
    const excelInput = container.querySelector<HTMLInputElement>(
      'input[type="file"][accept=".xlsx,.xlsm"]',
    );
    if (!imageInput || !excelInput) throw new Error("Expected image and Excel inputs.");

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:synthetic-image"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });

    const sheetsSpy = vi
      .spyOn(imageReplaceApi, "excelSheets")
      .mockResolvedValue({ sheets: ["Parts"] });
    vi.spyOn(imageReplaceApi, "excelColumns").mockResolvedValue({
      columns: [
        { index: 1, letter: "A", header: "Reference", label: "A — Reference" },
        { index: 2, letter: "B", header: "Description", label: "B — Description" },
        { index: 3, letter: "C", header: "Replacement", label: "C — Replacement" },
        { index: 4, letter: "D", header: "ICN", label: "D — ICN" },
        { index: 5, letter: "E", header: "Part", label: "E — Part" },
      ],
    });
    vi.spyOn(imageReplaceApi, "excelPieces").mockResolvedValue({
      pieces: [{ row: 2, name: "Pump A" }],
    });
    vi.spyOn(imageReplaceApi, "excelPairs").mockResolvedValue({
      pairs: [
        { reference: "R-001", replacement: "N-001" },
        { reference: "R-002", replacement: "N-002" },
      ],
    });
    const ocrResult: OcrResultDto = {
      width: 2480,
      height: 3508,
      source_width: 120,
      source_height: 60,
      full_text: "",
      lines: [],
      references: [],
      edited_image: "data:image/jpeg;base64,",
      filename: "ICN-A.jpg",
    };
    const ocrSpy = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(ocrResult);

    await screen.findByText("Sauvegarde locale à jour.");
    await user.upload(imageInput, new File(["synthetic image"], "source.png", { type: "image/png" }));
    await user.upload(
      excelInput,
      new File(["synthetic workbook"], "mapping.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );
    expect(sheetsSpy).toHaveBeenCalled();

    await user.selectOptions(await screen.findByLabelText("Onglet"), "Parts");
    await user.selectOptions(await screen.findByLabelText("Références à remplacer"), "1");
    await user.selectOptions(screen.getByLabelText("Nouveaux repères"), "3");
    await user.selectOptions(screen.getByLabelText("ICN (nom du JPG)"), "4");
    await user.selectOptions(screen.getByLabelText("Noms des pièces"), "5");
    await screen.findByRole("option", { name: "Pump A" });
    await user.selectOptions(screen.getByLabelText("Pièce à traiter"), "2");

    const excelReplacement = await screen.findByRole("textbox", {
      name: "Nouveau repère Excel 1",
    });
    await user.clear(excelReplacement);
    await user.type(excelReplacement, "N-009");
    await user.click(screen.getByRole("button", { name: "Supprimer le couple Excel 2" }));
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));

    expect(ocrSpy).toHaveBeenCalled();
    const formData = ocrSpy.mock.calls[0]?.[0];
    expect(formData?.get("excel_replacement_pairs")).toBe(
      JSON.stringify([{ reference: "R-001", replacement: "N-009" }]),
    );
  });
});
