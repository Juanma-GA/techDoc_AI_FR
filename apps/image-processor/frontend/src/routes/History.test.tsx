import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { WorkflowProvider } from "../hooks/WorkflowProvider";
import i18n from "../i18n";
import { imageReplaceApi } from "../lib/api";
import { workspaceApi, type WorkspaceSnapshot } from "../lib/workspace-api";
import { imageData, mockWorkspaceApi, ocrResult, preset } from "../test/workflow";
import { History } from "./History";
import { Home } from "./Home";

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  vi.stubGlobal("URL", class extends URL {
    static override createObjectURL() { return "blob:restored-original"; }
    static override revokeObjectURL() {}
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function renderHistory() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/history"]}>
        <WorkflowProvider>
          <Routes>
            <Route path="/history" element={<History />} />
            <Route path="/" element={<Home />} />
          </Routes>
        </WorkflowProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function seedHistory() {
  const mocks = mockWorkspaceApi();
  const { edited_image, ...analysis } = ocrResult;
  const state: WorkspaceSnapshot = {
    schema_version: 1,
    image: { name: "original.png", data_url: imageData },
    excel: {
      ...preset, pieceRow: "2",
      pairs: [{ id: 7, reference: "EDITED-REF", replacement: "CUSTOM", enabled: false }],
    },
    manualPairs: [{ id: 3, reference: "MANUAL", replacement: "TARGET", enabled: true }],
    revisions: [{
      kind: "ocr", image: { name: "edited.png", data_url: edited_image }, analysis,
    }],
    operations: [{ kind: "ocr", at: "2026-10-16T10:00:00Z" }],
  };
  await workspaceApi.save("c57ea9bc-780c-4586-a167-381ae2729601", state);
  return mocks;
}

it("restores the complete saved analysis, edits, selections, and undo without another OCR", async () => {
  const mocks = await seedHistory();
  const pairs = vi.spyOn(imageReplaceApi, "excelPairs");
  const ocr = vi.spyOn(imageReplaceApi, "runOcr");
  const user = userEvent.setup();
  renderHistory();
  await user.click(await screen.findByRole("button", { name: "Reprendre" }));
  expect(await screen.findByRole("heading", { name: "Détection et remplacement" })).toBeInTheDocument();
  expect(screen.getByLabelText("Description au point d’emploi")).toHaveValue("2");
  expect(await screen.findByRole("textbox", { name: "Référence Excel 1" })).toHaveValue("EDITED-REF");
  expect(screen.getByRole("textbox", { name: "Nouveau repère Excel 1" })).toHaveValue("CUSTOM");
  expect(screen.getByRole("checkbox", { name: "Appliquer le couple Excel 1" })).not.toBeChecked();
  expect(screen.getByRole("textbox", { name: "Référence à remplacer 1" })).toHaveValue("MANUAL");
  expect(screen.getByRole("img", { name: "Image résultante au format A4 portrait" })).toHaveAttribute("src", imageData);
  expect(pairs).not.toHaveBeenCalled();
  expect(ocr).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Annuler la dernière modification" }));
  await waitFor(() => expect(mocks.save.mock.lastCall?.[1].revisions).toHaveLength(0));
  expect(screen.getByRole("img", { name: "Image source pour PaddleOCR" }))
    .toHaveAttribute("src", "blob:restored-original");
});

it("requires a second click before deleting history", async () => {
  const mocks = await seedHistory();
  const user = userEvent.setup();
  renderHistory();
  await user.click(await screen.findByRole("button", { name: "Supprimer" }));
  expect(workspaceApi.remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Cliquer encore pour confirmer" }));
  await screen.findByText("Aucune image enregistrée pour le moment.");
  expect(mocks.entries.size).toBe(0);
});

it("reports a failed history load instead of opening an empty analysis", async () => {
  await seedHistory();
  vi.mocked(workspaceApi.read).mockRejectedValueOnce(new Error("Synthetic load failure"));
  const user = userEvent.setup();
  renderHistory();
  await user.click(await screen.findByRole("button", { name: "Reprendre" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic load failure");
  expect(screen.getByRole("heading", { name: "Historique" })).toBeInTheDocument();
});
