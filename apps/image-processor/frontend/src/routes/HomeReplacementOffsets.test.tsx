import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { Home } from "./Home";
import { imageData, mockWorkspaceApi, renderWorkflow } from "../test/workflow";

function dispatchPointer(
  element: Element,
  type: string,
  pointerId: number,
  clientX: number,
  clientY: number,
) {
  const event = new Event(type, { bubbles: true });
  Object.defineProperties(event, {
    pointerId: { value: pointerId },
    clientX: { value: clientX },
    clientY: { value: clientY },
  });
  fireEvent(element, event);
}

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
      }, {
        reference: "R-001", found: false, line_indices: [],
        replacement: "R-003",
      }],
      edited_image: imageData,
      filename: "source.jpg",
    };
    vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(result);
    const reapplySpy = vi.spyOn(imageReplaceApi, "reapplyReplacements").mockResolvedValue({
      edited_image: imageData,
      replacement_counts: [1, 0],
      partial_line_indices: [[0], []],
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

    const box = container.querySelector<SVGPolygonElement>("polygon[role='button']");
    if (!box) throw new Error("Expected the OCR box.");
    const svg = box.ownerSVGElement;
    if (!svg) throw new Error("Expected the OCR overlay.");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, left: 0, top: 0, right: 500, bottom: 700, width: 500, height: 700,
      toJSON: () => ({}),
    });
    dispatchPointer(box, "pointerdown", 1, 100, 100);
    dispatchPointer(box, "pointermove", 1, 120, 120);
    dispatchPointer(box, "pointerup", 1, 120, 120);
    fireEvent.click(box);
    expect(screen.queryByRole("group", { name: "Nouveau texte pour R-001" })).not.toBeInTheDocument();
    fireEvent.click(box);
    expect(await screen.findByRole("group", { name: "Nouveau texte pour R-001" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await user.click(screen.getByRole("button", { name: "Appliquer à tous les cadres remplacés" }));
    await user.click(screen.getByRole("button", { name: "Recalculer les remplacements" }));

    await waitFor(() => expect(reapplySpy).toHaveBeenCalledOnce());
    expect(await screen.findByText(
      "Une ligne contient cette référence dans un repère plus long ; elle ne sera pas remplacée.",
    )).toBeInTheDocument();
    const form = reapplySpy.mock.calls[0]?.[0];
    expect(form?.get("image")).toMatchObject({ name: "source.png" });
    expect(JSON.parse(String(form?.get("lines_json")))).toEqual([{
      text: "R-001",
      box: [[125, 125], [225, 125], [225, 155], [125, 155]],
    }]);
    expect(form?.get("broadcast_references_json")).toBe(JSON.stringify(["R-001"]));
    expect(JSON.parse(String(form?.get("replacement_pairs_json")))).toEqual([
      { reference: "R-001", replacement: "R-002" },
      { reference: "R-001", replacement: "R-003" },
    ]);
  });
});
