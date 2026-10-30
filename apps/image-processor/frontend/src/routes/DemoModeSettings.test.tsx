import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoModeProvider, useDemoMode } from "@internal/ui";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";

import { WorkflowProvider, useWorkflow } from "../hooks/WorkflowProvider";
import i18n from "../i18n";
import { imageReplaceApi, settingsApi, type SettingsDto } from "../lib/api";
import { emptyPreset, mockWorkspaceApi, preset } from "../test/workflow";
import { DemoModeSettings } from "./DemoModeSettings";

function DemoHomeProbe() {
  const workflow = useWorkflow();
  const { mode } = useDemoMode();
  const navigate = useNavigate();
  return (
    <section>
      <h1>Demo workspace</h1>
      <button
        type="button"
        disabled={!workflow.storage.ready}
        onClick={() => void workflow.chooseImage([
          new File(["normal image"], "normal.png", { type: "image/png" }),
        ])}
      >
        Load normal image
      </button>
      <button type="button" onClick={() => navigate("/settings")}>Open settings</button>
      <p data-testid="demo-image">{workflow.imageFile?.name ?? ""}</p>
      <p data-testid="demo-workbook">{workflow.excelFile?.name ?? ""}</p>
      <p data-testid="demo-mode">{mode}</p>
      <p data-testid="demo-mapping">
        {[
          workflow.excelSheet,
          workflow.excelReferenceColumn,
          workflow.excelReplacementColumn,
          workflow.excelIcnColumn,
          workflow.excelPieceColumn,
        ].join("|")}
      </p>
      <p data-testid="demo-piece-row">{workflow.excelPieceRow}</p>
      <p data-testid="demo-pieces">{workflow.excelPieces.map((piece) => piece.name).join("|")}</p>
    </section>
  );
}

function DemoModeTestApp() {
  const settings = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });

  return (
    <DemoModeProvider
      mode={settings.data?.demo_enabled ? "demo" : "normal"}
      isReady={settings.isSuccess}
    >
      <WorkflowProvider>
        <Routes>
          <Route path="/settings" element={<DemoModeSettings />} />
          <Route path="/" element={<DemoHomeProbe />} />
        </Routes>
      </WorkflowProvider>
    </DemoModeProvider>
  );
}

function renderDemoModeSettings(
  initialEntry = "/settings",
  initialPreset = emptyPreset,
) {
  const workspace = mockWorkspaceApi(initialPreset);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <DemoModeTestApp />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...rendered, workspace };
}

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  vi.spyOn(settingsApi, "read").mockResolvedValue({ demo_enabled: false });
  vi.stubGlobal("URL", class extends URL {
    static override createObjectURL() { return "blob:demo-image"; }
    static override revokeObjectURL() {}
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("demo mode import", () => {
  it("prefills the demo mapping, keeps demo edits volatile, and restores normal work", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) =>
      new Response(String(input), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    vi.spyOn(settingsApi, "write")
      .mockResolvedValueOnce({ demo_enabled: true })
      .mockResolvedValueOnce({ demo_enabled: false });
    const sheetsSpy = vi.spyOn(imageReplaceApi, "excelSheets").mockResolvedValue({
      sheets: ["Overview", "Parts", "Onglet 3"],
    });
    const columnsSpy = vi.spyOn(imageReplaceApi, "excelColumns").mockResolvedValue({
      columns: [
        { index: 3, letter: "C", header: "Reference", label: "C — Reference" },
        { index: 5, letter: "E", header: "Replacement", label: "E — Replacement" },
        { index: 30, letter: "AD", header: "ICN", label: "AD — ICN" },
        { index: 6, letter: "F", header: "Part", label: "F — Part" },
      ],
    });
    const piecesSpy = vi.spyOn(imageReplaceApi, "excelPieces").mockResolvedValue({
      pieces: [{ row: 9, name: "ROUE" }],
    });
    const ocrSpy = vi.spyOn(imageReplaceApi, "runOcr");
    const { workspace } = renderDemoModeSettings("/", preset);

    await screen.findByText("synthetic.xlsx");
    await user.click(screen.getByRole("button", { name: "Load normal image" }));
    await screen.findByText("normal.png");
    await user.click(screen.getByRole("button", { name: "Open settings" }));
    const demoButton = await screen.findByRole("button", { name: "Mode démo" });
    await waitFor(() => expect(demoButton).toBeEnabled());
    await user.click(demoButton);

    expect(await screen.findByRole("heading", { name: "Demo workspace" })).toBeInTheDocument();
    expect(screen.getByText("Image_roue.png")).toBeInTheDocument();
    expect(screen.getByText("DEMO_ROUE.xlsx")).toBeInTheDocument();
    expect(screen.getByTestId("demo-mapping")).toHaveTextContent("Onglet 3|3|5|30|6");
    expect(screen.getByTestId("demo-piece-row")).toBeEmptyDOMElement();
    expect(screen.getByTestId("demo-pieces")).toHaveTextContent("ROUE");
    expect(fetchSpy.mock.calls.map(([input]) => String(input))).toEqual([
      "/demo/Image_roue.png",
      "/demo/DEMO_ROUE.xlsx",
    ]);
    expect(sheetsSpy).toHaveBeenCalledOnce();
    expect(columnsSpy.mock.calls[0]?.[0].get("sheet_name")).toBe("Onglet 3");
    expect(piecesSpy.mock.calls[0]?.[0].get("reference_column")).toBe("3");
    expect(piecesSpy.mock.calls[0]?.[0].get("replacement_column")).toBe("5");
    expect(piecesSpy.mock.calls[0]?.[0].get("piece_column")).toBe("6");
    expect(ocrSpy).not.toHaveBeenCalled();
    expect(workspace.saveExcel.mock.calls.every(([state]) =>
      state.workbook?.name !== "DEMO_ROUE.xlsx",
    )).toBe(true);
    expect(workspace.save.mock.calls.every(([, state]) =>
      state.image.name !== "Image_roue.png",
    )).toBe(true);

    await user.click(screen.getByRole("button", { name: "Open settings" }));
    await user.click(screen.getByRole("button", { name: "Mode normal" }));

    expect(await screen.findByText("normal.png")).toBeInTheDocument();
    expect(screen.getByText("synthetic.xlsx")).toBeInTheDocument();
    expect(screen.getByTestId("demo-mapping")).toHaveTextContent("Parts|1|2|3|4");
    expect(workspace.saveExcel.mock.calls.every(([state]) =>
      state.workbook?.name !== "DEMO_ROUE.xlsx",
    )).toBe(true);
    expect(workspace.save.mock.calls.every(([, state]) =>
      state.image.name !== "Image_roue.png",
    )).toBe(true);
  });

  it("clears a demo workbook left by the previous persistent demo behavior", async () => {
    const user = userEvent.setup();
    vi.mocked(settingsApi.read).mockResolvedValue({ demo_enabled: true });
    vi.spyOn(settingsApi, "write").mockResolvedValue({ demo_enabled: false });
    const legacyDemoPreset = {
      ...preset,
      workbook: {
        ...preset.workbook!,
        name: "DEMO_ROUE.xlsx",
      },
    };
    const { workspace } = renderDemoModeSettings("/settings", legacyDemoPreset);

    const normalButton = await screen.findByRole("button", { name: "Mode normal" });
    await waitFor(() => expect(normalButton).toBeEnabled());
    await user.click(normalButton);

    expect(await screen.findByRole("heading", { name: "Demo workspace" })).toBeInTheDocument();
    expect(screen.getByTestId("demo-image")).toBeEmptyDOMElement();
    expect(screen.getByTestId("demo-workbook")).toBeEmptyDOMElement();
    expect(screen.getByTestId("demo-mode")).toHaveTextContent("normal");
    await waitFor(() => {
      expect(workspace.saveExcel.mock.calls.some(([state]) =>
        state.workbook === null,
      )).toBe(true);
    });
    expect(workspace.saveExcel.mock.calls.every(([state]) =>
      state.workbook?.name !== "DEMO_ROUE.xlsx",
    )).toBe(true);
  });

  it("shows a retryable error when a bundled demo asset cannot be loaded", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    vi.spyOn(settingsApi, "write").mockResolvedValue({ demo_enabled: true });
    renderDemoModeSettings("/settings");

    const demoButton = await screen.findByRole("button", { name: "Mode démo" });
    await waitFor(() => expect(demoButton).toBeEnabled());
    await user.click(demoButton);

    expect(await screen.findByRole("alert"))
      .toHaveTextContent(i18n.t("settings.demo.importError"));
    expect(screen.getByRole("button", { name: "Réessayer l’import" })).toBeEnabled();
    expect(screen.getByRole("heading", { name: i18n.t("settings.demo.title") }))
      .toBeInTheDocument();
  });
});
