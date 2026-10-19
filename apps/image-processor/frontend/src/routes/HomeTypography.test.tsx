import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { WorkflowProvider } from "../hooks/WorkflowProvider";
import i18n from "../i18n";
import { imageReplaceApi } from "../lib/api";
import { workspaceApi } from "../lib/workspace-api";
import {
  emptyPreset, imageData, mockWorkspaceApi, ocrResult, renderWorkflow,
} from "../test/workflow";
import { History } from "./History";
import { Home } from "./Home";

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  vi.stubGlobal("URL", class extends URL {
    static override createObjectURL() { return "blob:synthetic"; }
    static override revokeObjectURL() {}
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("reuses the first measured size on reruns and clears it when undo returns to the source", async () => {
  mockWorkspaceApi();
  const ocr = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue({
    ...ocrResult, replacement_font_size: 36,
  });
  const user = userEvent.setup();
  const { container } = renderWorkflow(<Home />);
  await screen.findByText("Sauvegarde locale à jour.");
  const input = container.querySelector<HTMLInputElement>('input[accept^="image/"]');
  if (!input) throw new Error("Synthetic upload missing.");
  await user.upload(input, new File(["synthetic"], "source.png", { type: "image/png" }));
  const submit = screen.getByRole("button", { name: "Lancer l’OCR sur CPU" });
  await user.click(submit);
  await waitFor(() => expect(ocr).toHaveBeenCalledTimes(1));
  expect(ocr.mock.calls[0]?.[0].has("replacement_font_size")).toBe(false);
  await user.click(submit);
  await waitFor(() => expect(ocr).toHaveBeenCalledTimes(2));
  expect(ocr.mock.calls[1]?.[0].get("replacement_font_size")).toBe("36");
  const undo = screen.getByRole("button", { name: "Annuler la dernière modification" });
  await user.click(undo);
  await user.click(undo);
  await user.click(submit);
  await waitFor(() => expect(ocr).toHaveBeenCalledTimes(3));
  expect(ocr.mock.calls[2]?.[0].has("replacement_font_size")).toBe(false);
});

it("reuses typography restored from history and never refetches it during reopening", async () => {
  mockWorkspaceApi();
  const { edited_image, ...analysis } = { ...ocrResult, replacement_font_size: 42 };
  await workspaceApi.save("c57ea9bc-780c-4586-a167-381ae2729601", {
    schema_version: 1, image: { name: "source.png", data_url: imageData },
    excel: { ...emptyPreset, pieceRow: "", pairs: [] }, manualPairs: [],
    revisions: [{ kind: "ocr", image: { name: "ICN-TEST.jpg", data_url: edited_image }, analysis }],
    operations: [{ kind: "ocr", at: "2026-10-16T10:00:00Z" }],
  });
  const ocr = vi.spyOn(imageReplaceApi, "runOcr").mockResolvedValue({ ...ocrResult, replacement_font_size: 42 });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
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
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Reprendre" }));
  await screen.findByRole("img", { name: "Image résultante au format A4 portrait" });
  expect(ocr).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" }));
  expect(ocr.mock.calls[0]?.[0].get("replacement_font_size")).toBe("42");
});
