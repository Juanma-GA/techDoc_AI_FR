import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import type { OcrResultDto } from "../lib/api";
import { ReplacementBoxControls } from "./ReplacementBoxControls";

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
    original_box: [[100, 100], [200, 100], [200, 130], [100, 130]],
    box_offset_x: 0,
    box_offset_y: 0,
    matched_references: ["R-001"],
  }],
  references: [{
    reference: "R-001", found: true, line_indices: [0],
    replacement: "R-002", replacement_count: 1,
  }],
  edited_image: "data:image/jpeg;base64,AA==",
  filename: "source.jpg",
};

beforeEach(async () => {
  await i18n.changeLanguage("fr");
});

afterEach(cleanup);

describe("replacement box controls", () => {
  it("offers to replace found references before the first replacement", () => {
    const onReapply = vi.fn();
    render(
      <ReplacementBoxControls
        result={{
          ...result,
          references: result.references.map((reference) => ({
            ...reference,
            replacement_count: undefined,
          })),
        }}
        selectedLineIndex={0}
        disabled={false}
        reapplyBlocked={false}
        onUpdateOffsets={vi.fn()}
        onApplyToAll={vi.fn()}
        onReapply={onReapply}
        t={i18n.t}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Remplacer" }));

    expect(onReapply).toHaveBeenCalledOnce();
  });

  it("updates the selected box and exposes apply-all and reapply actions", () => {
    const onUpdateOffsets = vi.fn();
    const onApplyToAll = vi.fn();
    const onReapply = vi.fn();
    render(
      <ReplacementBoxControls
        result={result}
        selectedLineIndex={0}
        disabled={false}
        reapplyBlocked={false}
        onUpdateOffsets={onUpdateOffsets}
        onApplyToAll={onApplyToAll}
        onReapply={onReapply}
        t={i18n.t}
      />,
    );

    fireEvent.change(screen.getByRole("slider", { name: "Décalage horizontal" }), {
      target: { value: "7" },
    });
    expect(onUpdateOffsets).toHaveBeenCalledWith([{ lineIndex: 0, x: 7, y: 0 }]);

    fireEvent.click(screen.getByRole("button", { name: "Appliquer à tous les cadres remplacés" }));
    fireEvent.click(screen.getByRole("button", { name: "Recalculer les remplacements" }));
    expect(onApplyToAll).toHaveBeenCalledOnce();
    expect(onReapply).toHaveBeenCalledOnce();
  });
});
