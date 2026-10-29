import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoModeProvider } from "@internal/ui";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { WorkflowProvider, useWorkflow } from "../hooks/WorkflowProvider";
import i18n from "../i18n";
import { imageReplaceApi, settingsApi, type SettingsDto } from "../lib/api";
import { mockWorkspaceApi } from "../test/workflow";
import { DemoModeSettings } from "./DemoModeSettings";

function DemoHomeProbe() {
  const workflow = useWorkflow();
  return (
    <section>
      <h1>Demo workspace</h1>
      {workflow.imageFile ? <p>{workflow.imageFile.name}</p> : null}
      {workflow.excelFile ? <p>{workflow.excelFile.name}</p> : null}
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

function renderDemoModeSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings"]}>
        <DemoModeTestApp />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("fr");
  mockWorkspaceApi();
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
  it("loads both bundled files into the workspace and opens Home without running OCR", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) =>
      new Response(String(input), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    vi.spyOn(settingsApi, "write").mockResolvedValue({ demo_enabled: true });
    const sheetsSpy = vi.spyOn(imageReplaceApi, "excelSheets").mockResolvedValue({
      sheets: ["ROUE"],
    });
    const ocrSpy = vi.spyOn(imageReplaceApi, "runOcr");
    renderDemoModeSettings();

    const demoButton = await screen.findByRole("button", { name: "Mode démo" });
    await waitFor(() => expect(demoButton).toBeEnabled());
    await user.click(demoButton);

    expect(await screen.findByRole("heading", { name: "Demo workspace" })).toBeInTheDocument();
    expect(screen.getByText("Image_roue.png")).toBeInTheDocument();
    expect(screen.getByText("DEMO_ROUE.xlsx")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.map(([input]) => String(input))).toEqual([
      "/demo/Image_roue.png",
      "/demo/DEMO_ROUE.xlsx",
    ]);
    expect(sheetsSpy).toHaveBeenCalledOnce();
    expect(ocrSpy).not.toHaveBeenCalled();
  });

  it("shows a retryable error when a bundled demo asset cannot be loaded", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    vi.spyOn(settingsApi, "write").mockResolvedValue({ demo_enabled: true });
    renderDemoModeSettings();

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
