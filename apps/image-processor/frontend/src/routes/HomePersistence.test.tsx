import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { imageReplaceApi } from "../lib/api";
import { storeFile } from "../lib/workspace-api";
import { mockWorkspaceApi, ocrResult, preset, renderWorkflow } from "../test/workflow";
import { Home } from "./Home";

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  vi.stubGlobal("URL", class extends URL {
    static override createObjectURL() { return "blob:synthetic"; }
    static override revokeObjectURL() {}
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function uploadImage(user: ReturnType<typeof userEvent.setup>, container: HTMLElement, name = "source.png") {
  const input = container.querySelector<HTMLInputElement>('input[accept^="image/"]');
  if (!input) throw new Error("Image input missing.");
  await user.upload(input, new File(["synthetic original"], name, { type: "image/png" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Nouvelle image" })).toBeEnabled());
}

describe("startup preferences and progressive replacements", () => {
  it("restores workbook and columns, never the image or part, including after a remount", async () => {
    const mocks = mockWorkspaceApi(preset);
    const pairs = vi.spyOn(imageReplaceApi, "excelPairs").mockResolvedValue({
      pairs: [{ reference: "R-1", replacement: "N-1" }],
    });
    const user = userEvent.setup();
    const first = renderWorkflow(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");
    expect(screen.getByText("synthetic.xlsx")).toBeInTheDocument();
    expect(screen.getByLabelText("Onglet")).toHaveValue("Parts");
    expect(screen.getByLabelText("Références à remplacer")).toHaveValue("1");
    expect(screen.getByLabelText("Nouveaux repères")).toHaveValue("2");
    expect(screen.getByLabelText("ICN (nom du JPG)")).toHaveValue("3");
    expect(screen.getByLabelText("Noms des pièces")).toHaveValue("4");
    expect(screen.getByLabelText("Description au point d’emploi")).toHaveValue("");
    expect(screen.getByText("Choisir une image")).toBeInTheDocument();
    expect(pairs).not.toHaveBeenCalled();

    await uploadImage(user, first.container);
    await user.selectOptions(screen.getByLabelText("Description au point d’emploi"), "2");
    await screen.findByRole("textbox", { name: "Référence Excel 1" });
    await waitFor(() => expect(mocks.save.mock.lastCall?.[1].excel.pieceRow).toBe("2"));
    const saved = mocks.saveExcel.mock.lastCall?.[0];
    expect(saved).not.toHaveProperty("pieceRow");
    expect(saved).not.toHaveProperty("image");
    expect(saved?.workbook?.name).toBe("synthetic.xlsx");
    first.unmount();

    renderWorkflow(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");
    expect(screen.getByLabelText("Description au point d’emploi")).toHaveValue("");
    expect(screen.getByText("Choisir une image")).toBeInTheDocument();
    expect(screen.getByLabelText("Noms des pièces")).toHaveValue("4");
  });

  it("submits only selected pairs and reruns on the last result; failure leaves it intact", async () => {
    mockWorkspaceApi();
    const ocr = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(ocrResult);
    const user = userEvent.setup();
    const { container } = renderWorkflow(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");
    await uploadImage(user, container);
    for (const number of [1, 2]) {
      await user.click(screen.getByRole("button", { name: "Ajouter un couple" }));
      await user.type(screen.getByRole("textbox", { name: `Référence à remplacer ${number}` }), `R-${number}`);
      await user.type(screen.getByRole("textbox", { name: `Nouveau repère ${number}` }), `N-${number}`);
    }
    await user.click(screen.getByRole("checkbox", { name: "Appliquer le couple 2" }));
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
    expect(ocr.mock.calls[0]?.[0].get("replacement_pairs")).toBe(
      JSON.stringify([{ reference: "R-1", replacement: "N-1" }]),
    );
    await user.click(screen.getByRole("checkbox", { name: "Appliquer le couple 1" }));
    await user.click(screen.getByRole("checkbox", { name: "Appliquer le couple 2" }));
    ocr.mockRejectedValueOnce(new Error("Synthetic OCR failure"));
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic OCR failure");
    const uploaded = ocr.mock.calls[1]?.[0].get("image");
    if (!(uploaded instanceof File)) throw new Error("Expected the current image file.");
    expect(uploaded.name).toBe("source.png");
    expect((await storeFile(uploaded)).data_url).toBe(ocrResult.edited_image);
    expect(ocr.mock.calls[1]?.[0].get("replacement_pairs")).toBe(
      JSON.stringify([{ reference: "R-2", replacement: "N-2" }]),
    );
    expect(screen.getByRole("img", { name: "Image résultante au format A4 portrait" }))
      .toHaveAttribute("src", ocrResult.edited_image);
    await user.click(screen.getByRole("button", { name: "Annuler la dernière modification" }));
    expect(screen.getByRole("img", { name: "Image source pour PaddleOCR" })).toHaveAttribute("src", "blob:synthetic");
  });

  it("selectively applies Excel pairs without deleting the unselected pair", async () => {
    const mocks = mockWorkspaceApi(preset);
    vi.spyOn(imageReplaceApi, "excelPairs").mockResolvedValue({
      pairs: [{ reference: "R-1", replacement: "N-1" }, { reference: "R-2", replacement: "N-2" }],
    });
    const ocr = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(ocrResult);
    const user = userEvent.setup();
    const { container } = renderWorkflow(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");
    await uploadImage(user, container);
    await user.selectOptions(screen.getByLabelText("Description au point d’emploi"), "2");
    await waitFor(() => expect(ocr).toHaveBeenCalledOnce());
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" })).toBeEnabled();
    });
    await user.click(await screen.findByRole("checkbox", { name: "Appliquer le couple Excel 1" }));
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
    await waitFor(() => expect(ocr).toHaveBeenCalledTimes(2));
    expect(ocr.mock.calls[1]?.[0].get("excel_replacement_pairs")).toBe(
      JSON.stringify([{ reference: "R-2", replacement: "N-2" }]),
    );
    expect(ocr.mock.calls[0]?.[0].get("comparison_only")).toBe("true");
    await waitFor(() => expect(mocks.save.mock.lastCall?.[1].excel.pairs[0]?.enabled).toBe(false));
    expect(screen.getByRole("textbox", { name: "Référence Excel 1" })).toHaveValue("R-1");
  });
});
