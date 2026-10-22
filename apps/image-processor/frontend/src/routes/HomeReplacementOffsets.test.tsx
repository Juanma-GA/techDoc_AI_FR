import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { Home } from "./Home";
import { imageData, mockWorkspaceApi, renderWorkflow } from "../test/workflow";

describe("Home replacement box offsets", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("fr");
    mockWorkspaceApi();
    vi.stubGlobal("URL", class extends URL {
      static override createObjectURL() { return "blob:synthetic"; }
      static override revokeObjectURL() {}
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("reapplies shifted boxes from the original image", async () => {
    const user = userEvent.setup();
    const result: OcrResultDto = {
      width: 2480,
      height: 3508,
      source_width: 2480,
      source_height: 3508,
      full_text: "R-001",
      lines: [{
        text: "R-001",
        confidence: 1,
        box: [[100, 100], [200, 100], [200, 130], [100, 130]],
        matched_references: ["R-001"],
      }],
      references: [{
        reference: "R-001", found: true, line_indices: [0],
        replacement: "R-002", replacement_count: 1,
      }],
      edited_image: imageData,
      filename: "source.jpg",
    };
    vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(result);
    const reapplySpy = vi.spyOn(imageReplaceApi, "reapplyReplacements").mockResolvedValue({
      edited_image: imageData,
      replacement_counts: [1],
      replacement_font_size: null,
    });
    const source = new File(["synthetic image"], "source.png", { type: "image/png" });
    const { container } = renderWorkflow(<Home />);
    await screen.findByText("Sauvegarde locale à jour.");

    const imageInput = container.querySelector<HTMLInputElement>('input[type="file"][accept^="image/"]');
    if (!imageInput) throw new Error("Expected the image input.");
    await user.upload(imageInput, source);
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
    await waitFor(() => expect(container.querySelector("polygon[role='button']")).not.toBeNull());

    const box = container.querySelector("polygon[role='button']");
    if (!box) throw new Error("Expected the OCR box.");
    fireEvent.click(box);
    fireEvent.change(screen.getByRole("slider", { name: "Décalage horizontal" }), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByRole("slider", { name: "Décalage vertical" }), {
      target: { value: "-4" },
    });
    await user.click(screen.getByRole("button", { name: "Appliquer à tous les cadres remplacés" }));
    await user.click(screen.getByRole("button", { name: "Recalculer les remplacements" }));

    await waitFor(() => expect(reapplySpy).toHaveBeenCalledOnce());
    const form = reapplySpy.mock.calls[0]?.[0];
    expect(form?.get("image")).toMatchObject({ name: "source.png" });
    expect(JSON.parse(String(form?.get("lines_json")))).toEqual([{
      text: "R-001",
      box: [[108, 96], [208, 96], [208, 126], [108, 126]],
    }]);
  });
});
