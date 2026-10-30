import { cleanup, render as renderUi, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { OcrResults } from "../components/OcrResults";
import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import { Home } from "./Home";
import { imageData, mockWorkspaceApi, renderWorkflow as render } from "../test/workflow";

const originalUrlMethodDescriptors = new Map(
  ["createObjectURL", "revokeObjectURL"].map((method) => [
    method,
    Object.getOwnPropertyDescriptor(URL, method),
  ]),
);

describe("recognized text replacement", () => {
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

  it("updates a recognized line in place without running OCR again and keeps it undoable", async () => {
    const user = userEvent.setup();
    const { container } = render(<Home />);
    const imageInput = container.querySelector<HTMLInputElement>(
      'input[type="file"][accept^="image/"]',
    );
    if (!imageInput) throw new Error("Expected an image input.");

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:synthetic-image"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });

    const ocrResult: OcrResultDto = {
      width: 2480,
      height: 3508,
      source_width: 120,
      source_height: 60,
      full_text: "K555",
      lines: [{
        text: "K555",
        confidence: 0.99,
        box: [[100, 100], [200, 100], [200, 130], [100, 130]],
        matched_references: [],
      }],
      references: [],
      edited_image: imageData,
      filename: "ICN-A.jpg",
    };
    const runOcr = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue(ocrResult);
    const replaceLine = vi.spyOn(imageReplaceApi, "replaceLine").mockResolvedValue({
      edited_image: "data:image/jpeg;base64,c3ludGhldGlj",
      replacement_count: 1,
      replacement_font_size: 12,
    });

    await screen.findByText("Sauvegarde locale à jour.");
    await user.upload(
      imageInput,
      new File(["synthetic image"], "source.png", { type: "image/png" }),
    );
    await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
    const clickableLineTargets = await screen.findAllByRole("button", {
      name: "Remplacer la ligne K555",
    });
    const boxButton = clickableLineTargets[0];
    if (!boxButton) throw new Error("Expected an OCR box button.");
    await user.click(boxButton);

    const abandonedInput = screen.getByRole("textbox", { name: "Nouveau texte pour K555" });
    await user.type(abandonedInput, "K000");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("textbox", { name: "Nouveau texte pour K555" })).not.toBeInTheDocument();

    const recognizedLineButton = screen.getAllByRole("button", {
      name: "Remplacer la ligne K555",
    }).at(-1);
    if (!recognizedLineButton) throw new Error("Expected a recognized-line edit button.");
    await user.click(recognizedLineButton);
    const replacementInput = screen.getByRole("textbox", { name: "Nouveau texte pour K555" });
    await user.type(replacementInput, "K777");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(replaceLine).toHaveBeenCalledOnce());
    expect(runOcr).toHaveBeenCalledOnce();
    const form = replaceLine.mock.calls[0]?.[0];
    expect(form?.get("reference")).toBe("K555");
    expect(form?.get("replacement")).toBe("K777");
    expect(JSON.parse(String(form?.get("line_json")))).toEqual({
      text: "K555",
      box: ocrResult.lines[0]?.box,
    });
    expect(screen.getByRole("img", { name: "Image résultante au format A4 portrait" }))
      .toHaveAttribute("src", "data:image/jpeg;base64,c3ludGhldGlj");
    expect(screen.getByRole("textbox", { name: "Référence à remplacer 1" })).toHaveValue("K555");
    expect(screen.getByRole("textbox", { name: "Nouveau repère 1" })).toHaveValue("K777");

    await user.click(screen.getByRole("button", { name: "Annuler la dernière modification" }));
    await waitFor(() => {
      expect(screen.getByRole("img", { name: "Image résultante au format A4 portrait" }))
        .toHaveAttribute("src", imageData);
    });
  });

  it("provides the same accessible editing controls in English", async () => {
    const user = userEvent.setup();
    await i18n.changeLanguage("en");
    const result: OcrResultDto = {
      width: 2480,
      height: 3508,
      source_width: 120,
      source_height: 60,
      full_text: "K555",
      lines: [{
        text: "K555",
        confidence: 0.99,
        box: [[100, 100], [200, 100], [200, 130], [100, 130]],
        matched_references: [],
      }],
      references: [],
      edited_image: imageData,
      filename: "synthetic.jpg",
    };
    const onReplaceLine = vi.fn(async () => true);
    renderUi(
      <OcrResults
        result={result}
        disabled={false}
        selectionRequest={null}
        onSelectionHandled={vi.fn()}
        onReplaceLine={onReplaceLine}
        onUndoLine={vi.fn(async () => false)}
        t={i18n.getFixedT("en")}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Replace line K555" }));
    const replacementInput = screen.getByRole("textbox", { name: "New text for K555" });
    await user.type(replacementInput, "K777");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(onReplaceLine).toHaveBeenCalledWith(0, "K555", "K777", null));
  });

  it("warns when a reference is present only inside a longer OCR token", () => {
    const result: OcrResultDto = {
      width: 2480,
      height: 3508,
      source_width: 120,
      source_height: 80,
      full_text: "34708SM\n34708SM2",
      lines: [
        {
          text: "34708SM",
          confidence: 0.99,
          box: [[100, 100], [200, 100], [200, 130], [100, 130]],
          matched_references: ["34708SM"],
        },
        {
          text: "34708SM2",
          confidence: 0.99,
          box: [[100, 140], [210, 140], [210, 170], [100, 170]],
          matched_references: [],
        },
      ],
      references: [{
        reference: "34708SM",
        found: true,
        line_indices: [0],
        partial_line_indices: [1],
        replacement: "28",
        replacement_count: 1,
      }],
      edited_image: imageData,
      filename: "synthetic.jpg",
    };

    const { rerender } = renderUi(
      <OcrResults
        result={result}
        disabled={false}
        selectionRequest={null}
        onSelectionHandled={vi.fn()}
        onReplaceLine={vi.fn(async () => true)}
        onUndoLine={vi.fn(async () => false)}
        t={i18n.getFixedT("fr")}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Une ligne contient cette référence dans un repère plus long ; elle ne sera pas remplacée.",
    );

    rerender(
      <OcrResults
        result={result}
        disabled={false}
        selectionRequest={null}
        onSelectionHandled={vi.fn()}
        onReplaceLine={vi.fn(async () => true)}
        onUndoLine={vi.fn(async () => false)}
        t={i18n.getFixedT("en")}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "One line contains this reference inside a longer token; it will be left unchanged.",
    );
  });
});
