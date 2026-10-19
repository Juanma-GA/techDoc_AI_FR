import type { Page } from "@playwright/test";

import type {
  ExcelPreset, HistoryDetail, HistorySummary, WorkspaceSnapshot,
} from "../../src/lib/workspace-api";

export const excelPreset: ExcelPreset = {
  workbook: {
    name: "synthetic.xlsx",
    data_url: `data:application/octet-stream;base64,${Buffer.from("synthetic workbook").toString("base64")}`,
  },
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
const emptyPreset: ExcelPreset = {
  workbook: null, sheets: [], sheet: "", columns: [], referenceColumn: "",
  replacementColumn: "", icnColumn: "", pieceColumn: "", pieces: [],
};

export async function mockWorkspace(page: Page, initialPreset = emptyPreset) {
  let preset = initialPreset;
  const entries = new Map<string, HistoryDetail>();
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (path === "/api/v1/settings") return route.fulfill({ json: { demo_enabled: false } });
    if (path === "/api/v1/image-processor/workspace/excel") {
      if (method === "PUT") preset = request.postDataJSON();
      return route.fulfill({ json: preset });
    }
    if (path === "/api/v1/image-processor/history") {
      const items = [...entries.values()].map(({ state: _state, ...metadata }) => metadata);
      return route.fulfill({ json: { items, next_cursor: null } });
    }
    const id = path.match(/^\/api\/v1\/image-processor\/history\/([^/]+)$/)?.[1];
    if (id) {
      if (method === "PUT") {
        const state: WorkspaceSnapshot = request.postDataJSON();
        const summary: HistorySummary = {
          id, filename: state.excel.pieceRow === "2"
            ? "ICN-TEST.jpg"
            : state.revisions.at(-1)?.analysis?.filename ?? state.image.name,
          piece_name: state.excel.pieces.find((piece) => String(piece.row) === state.excel.pieceRow)?.name ?? "",
          created_at: "2026-10-16T10:00:00Z", updated_at: "2026-10-16T10:00:00Z",
          version: (entries.get(id)?.version ?? 0) + 1, operation_count: state.operations.length,
        };
        entries.set(id, { ...summary, state });
        return route.fulfill({ json: summary });
      }
      if (method === "DELETE") {
        entries.delete(id);
        return route.fulfill({ status: 204 });
      }
      const entry = entries.get(id);
      return route.fulfill({ status: entry ? 200 : 404, json: entry ?? { message: "Not found" } });
    }
    return route.fulfill({ status: 501, json: { message: "Unexpected synthetic test endpoint." } });
  });
  return { entries, getPreset: () => preset };
}

export async function syntheticImages(page: Page): Promise<[string, string, string]> {
  return page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 100;
    canvas.height = 80;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas unavailable.");
    const images: string[] = [];
    for (const value of ["R-1 R-2", "N-1 R-2", "N-1"]) {
      context.fillStyle = "white";
      context.fillRect(0, 0, 100, 80);
      context.fillStyle = "black";
      context.fillText(value, 15, 40);
      images.push(canvas.toDataURL("image/png"));
    }
    return [images[0]!, images[1]!, images[2]!];
  });
}
