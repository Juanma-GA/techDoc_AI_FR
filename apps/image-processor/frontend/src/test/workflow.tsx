import { render, screen, type RenderResult } from "@testing-library/react";
import type userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { vi } from "vitest";

import { WorkflowProvider } from "../hooks/WorkflowProvider";
import { imageReplaceApi, type OcrResultDto } from "../lib/api";
import {
  workspaceApi, type ExcelPreset, type HistoryDetail, type HistorySummary, type WorkspaceSnapshot,
} from "../lib/workspace-api";

export const imageData =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/GNcAAAAASUVORK5CYII=";
export const emptyPreset: ExcelPreset = {
  workbook: null, sheets: [], sheet: "", columns: [], referenceColumn: "",
  replacementColumn: "", icnColumn: "", pieceColumn: "", pieces: [],
};
export const preset: ExcelPreset = {
  workbook: { name: "synthetic.xlsx", data_url: `data:application/octet-stream;base64,${btoa("workbook")}` },
  sheets: ["Parts"], sheet: "Parts",
  columns: [
    { index: 1, letter: "A", header: "Reference", label: "A Reference" },
    { index: 2, letter: "B", header: "Replacement", label: "B Replacement" },
    { index: 3, letter: "C", header: "ICN", label: "C ICN" },
    { index: 4, letter: "D", header: "Part", label: "D Part" },
  ],
  referenceColumn: "1", replacementColumn: "2", icnColumn: "3", pieceColumn: "4",
  pieces: [{ row: 2, name: "Synthetic pump" }],
};
export const ocrResult: OcrResultDto = {
  width: 2480, height: 3508, source_width: 1, source_height: 1,
  full_text: "R-1", lines: [], references: [],
  edited_image: imageData, filename: "edited.png",
};

function summary(id: string, state: WorkspaceSnapshot, version: number): HistorySummary {
  return {
    id, filename: state.image.name,
    piece_name: state.excel.pieces.find((piece) => String(piece.row) === state.excel.pieceRow)?.name ?? "",
    created_at: "2026-10-16T10:00:00Z", updated_at: "2026-10-16T10:00:00Z",
    version, operation_count: state.operations.length,
  };
}

export function mockWorkspaceApi(initialPreset = emptyPreset) {
  let savedPreset = initialPreset;
  const entries = new Map<string, HistoryDetail>();
  const readExcel = vi.spyOn(workspaceApi, "readExcel").mockImplementation(async () => savedPreset);
  const saveExcel = vi.spyOn(workspaceApi, "saveExcel").mockImplementation(async (state) => {
    savedPreset = state;
    return state;
  });
  const save = vi.spyOn(workspaceApi, "save").mockImplementation(async (id, state) => {
    const metadata = summary(id, state, (entries.get(id)?.version ?? 0) + 1);
    entries.set(id, { ...metadata, state });
    return metadata;
  });
  vi.spyOn(workspaceApi, "read").mockImplementation(async (id) => {
    const entry = entries.get(id);
    if (!entry) throw new Error("History entry not found.");
    return entry;
  });
  vi.spyOn(workspaceApi, "list").mockImplementation(async () => ({
    items: [...entries.values()].map(({ state: _state, ...metadata }) => metadata),
    next_cursor: null,
  }));
  vi.spyOn(workspaceApi, "remove").mockImplementation(async (id) => { entries.delete(id); });
  return { entries, readExcel, saveExcel, save };
}

export function renderWorkflow(ui: ReactElement): RenderResult {
  return render(<WorkflowProvider>{ui}</WorkflowProvider>);
}

export async function selectExcelPartInHome(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
) {
  await screen.findByText("Sauvegarde locale à jour.");
  const excelInput = container.querySelector<HTMLInputElement>(
    'input[type="file"][accept=".xlsx,.xlsm"]',
  );
  if (!excelInput) throw new Error("Expected an Excel input.");
  vi.spyOn(imageReplaceApi, "excelSheets").mockResolvedValue({ sheets: ["Parts"] });
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
  await user.upload(
    excelInput,
    new File(["synthetic workbook"], "mapping.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
  );
  await user.selectOptions(await screen.findByLabelText("Onglet"), "Parts");
  await user.selectOptions(await screen.findByLabelText("Références à remplacer"), "1");
  await user.selectOptions(screen.getByLabelText("Nouveaux repères"), "3");
  await user.selectOptions(screen.getByLabelText("ICN (nom du JPG)"), "4");
  await user.selectOptions(screen.getByLabelText("Noms des pièces"), "5");
  await screen.findByRole("option", { name: "Pump A" });
  await user.selectOptions(screen.getByLabelText("Pièce à traiter"), "2");
}
