import { notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MistralForm } from "../components/settings/MistralForm";
import { CustomRulesCard } from "../components/settings/CustomRulesCard";
import { ChecklistImportCard } from "../components/settings/ChecklistImportCard";
import { SpecGenerateCard } from "../components/settings/SpecGenerateCard";
import { anomaliesApi, filesApi, healthApi, kpisApi, projectsApi, referenceApi, settingsApi } from "../lib/api";
import type { AnomalyOut, FileOut, ProjectOut } from "../lib/types";
import { useScopeStore } from "../stores/useScopeStore";
import { Knowledge } from "./Knowledge";
import { Manager } from "./Manager";
import { Redacteur } from "./Redacteur";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

const projects: ProjectOut[] = ["a", "b"].map((id) => ({
  id, name: `Project ${id}`, description: "", vision_enabled: false, created_at: "",
}));
const file = (id: string): FileOut => ({
  id: `file-${id}`, current_name: `${id}.xlsx`, rel_path: null, mime_type: "", created_at: "",
  versions: [{ id: `version-${id}`, filename: `${id}.xlsx`, sha256: "", size: 1, uploaded_at: "" }],
});
const anomaly = (id: string, status: AnomalyOut["status"] = "open"): AnomalyOut => ({
  id: `ticket-${id}`, project_id: id, file_version_id: `version-${id}`, run_id: null,
  type: "personnalisee", category: "Safety", severity: "high", confidence: "elevee",
  message: `Warning ${id}`, suggestion: "Add a warning", evidence: "Synthetic evidence",
  message_key: null, message_params_json: null, suggestion_key: null, suggestion_params_json: null,
  location: "", status, created_at: "", resolved_at: status === "fixed" ? "2026-10-01T10:00:00Z" : null,
});

let container: HTMLDivElement;
let root: Root;
let client: QueryClient;

async function settle() {
  await vi.waitFor(async () => {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
    expect(container.childElementCount).toBeGreaterThan(0);
    const loading = [...container.querySelectorAll(".empty-state")].filter((node) =>
      !node.closest("[hidden]") && node.textContent === "common.loading",
    );
    expect(loading).toHaveLength(0);
    expect(client.isFetching()).toBe(0);
  });
}

async function render(element: ReactNode) {
  await act(async () => {
    root.render(<QueryClientProvider client={client}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{element}</MemoryRouter>
    </QueryClientProvider>);
  });
  await settle();
}

async function click(button: Element | undefined | null) {
  expect(button).toBeInstanceOf(HTMLButtonElement);
  await act(async () => { button?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  notifyManager.setNotifyFunction((callback) => { act(callback); });
  useScopeStore.setState({ managerScope: [], redacteurProjectId: null });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(projectsApi, "list").mockResolvedValue(projects);
  vi.spyOn(filesApi, "list").mockImplementation(async (id) => [file(id)]);
  vi.spyOn(filesApi, "getFolder").mockResolvedValue({ path: null });
  vi.spyOn(referenceApi, "get").mockResolvedValue({ path: "synthetic.xlsx", sheets: [], columns: [], header_rows: {}, analysis_run_id: null });
  vi.spyOn(referenceApi, "basl").mockResolvedValue({ path: null, sheets: [], columns: [], header_rows: {}, analysis_run_id: null });
  vi.spyOn(settingsApi, "rulesLegacy").mockResolvedValue({ rules: { regles_personnalisees: [] }, overridden: false });
  vi.spyOn(healthApi, "read").mockResolvedValue({ status: "ok", version: "", db: "ok", llm: "disabled" });
  vi.spyOn(healthApi, "connectivity").mockResolvedValue({
    checked_at: "2026-11-04T10:00:00Z", ai_enabled: false, ai_connection: "disabled",
    sources: {
      documents: { configured: 2, available: 2, unavailable: 0 },
      folder: { configured: 0, available: 0, unavailable: 0 },
      reference: { configured: 1, available: 1, unavailable: 0 },
      basl: { configured: 0, available: 0, unavailable: 0 },
    },
  });
  vi.spyOn(anomaliesApi, "list").mockImplementation(async (id) => [anomaly(id)]);
  vi.spyOn(anomaliesApi, "rejectionsSummary").mockResolvedValue({
    total: 0, by_category: [], items: [], synthese: "", llm_used: false, cached: false, generated_at: "",
  });
  vi.spyOn(kpisApi, "scope").mockResolvedValue({
    open_anomalies: 2, anomalies_by_severity: {}, anomalies_by_type: {}, anomalies_by_category: {},
    anomalies_by_status: {}, anomalies_by_confidence: {}, resolution_rate: 0, anomalies_over_time: [],
    top_files: [], top_rules: [], avg_age_days: 0, avg_resolution_days: 0, files_total: 2, files_with_anomalies: 2,
  });
});

afterEach(async () => {
  await act(async () => root.unmount());
  client.clear();
  container.remove();
  vi.restoreAllMocks();
  notifyManager.setNotifyFunction((callback) => { callback(); });
  vi.unstubAllGlobals();
});

it("translates checklist severities without changing submitted machine values", async () => {
  vi.mocked(settingsApi.rulesLegacy).mockResolvedValue({
    rules: { regles_personnalisees: [{ id: "synthetic", label: "Synthetic rule", consigne: "Check fixture", severity: "high" }] },
    overridden: true,
  });
  await render(<CustomRulesCard />);
  const options = [...container.querySelectorAll<HTMLOptionElement>("select option")];
  expect(options.map((option) => option.textContent)).toEqual([
    "redacteur.sevLow", "redacteur.sevMedium", "redacteur.sevHigh",
  ]);
  expect(options.map((option) => option.value)).toEqual(["low", "medium", "high"]);
});

it("uses translated file pickers while preserving checklist inspection and proposal generation", async () => {
  vi.spyOn(settingsApi, "rulesInspect").mockResolvedValue({ sheets: [] });
  vi.spyOn(settingsApi, "rulesFromSpec").mockResolvedValue({
    count: 1, regles: [{ label: "Synthetic", consigne: "Check fixture", severity: "high" }],
  });
  await render(<><ChecklistImportCard /><SpecGenerateCard /></>);
  expect(container.textContent).toContain("settings.chooseChecklist");
  expect(container.textContent).toContain("settings.chooseReference");
  const inputs = [...container.querySelectorAll<HTMLInputElement>('input[type="file"]')];
  const files = [new File(["Synthetic"], "synthetic.xlsx"), new File(["Synthetic"], "synthetic.txt")];
  await act(async () => {
    inputs.forEach((input, index) => {
      expect(input.classList.contains("hidden")).toBe(true);
      Object.defineProperty(input, "files", { configurable: true, value: [files[index]] });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
  await settle();
  expect(settingsApi.rulesInspect).toHaveBeenCalledWith(files[0]);
  expect(settingsApi.rulesFromSpec).toHaveBeenCalledWith(files[1]);
  expect(container.textContent).toContain("synthetic.xlsx");
  expect(container.textContent).toContain("synthetic.txt");
  expect(container.textContent).toContain("redacteur.sevHigh");
});

describe("ticket placement", () => {
  it("keeps ticket lists off the dashboard even when a project is selected", async () => {
    await render(<Manager />);
    expect(container.textContent).toContain("manager.kpis");
    expect(container.textContent).not.toContain("tickets.title");
    expect(container.querySelector(".red-status-select")).toBeNull();
    expect(anomaliesApi.list).not.toHaveBeenCalled();
    await click([...container.querySelectorAll(".slicer button")].find((button) => button.textContent === "Project b"));
    expect(container.querySelector(".red-status-select")).toBeNull();
    expect(anomaliesApi.list).not.toHaveBeenCalled();
  });

  it("shows all editor file groups collapsed and filters to the selected project", async () => {
    await render(<Redacteur />);
    expect(container.querySelectorAll("button[aria-expanded=false]")).toHaveLength(2);
    expect(container.textContent).toContain("a.xlsx (1)");
    expect(container.textContent).toContain("b.xlsx (1)");
    await click(container.querySelector("button[aria-expanded=false]"));
    expect(container.querySelectorAll("button[aria-expanded=true]")).toHaveLength(1);
    const projectSelect = container.querySelector("select");
    await act(async () => {
      if (projectSelect) {
        projectSelect.value = "b";
        projectSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    await settle();
    expect(container.textContent).not.toContain("a.xlsx");
    expect(container.textContent).toContain("b.xlsx");
    expect(container.querySelectorAll("button[aria-expanded=false]")).toHaveLength(1);
    await act(async () => {
      if (projectSelect) {
        projectSelect.value = "";
        projectSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    await settle();
    expect(container.querySelectorAll("button[aria-expanded=false]")).toHaveLength(2);
  });

  it("defaults the editor to all projects and exposes request failures", async () => {
    vi.mocked(anomaliesApi.list).mockRejectedValue(new Error("Synthetic source failure"));
    await render(<Redacteur />);
    expect(container.querySelector("select")?.value).toBe("");
    expect(container.querySelector("[role=alert]")?.textContent).toContain("Synthetic source failure");
    expect(filesApi.list).toHaveBeenCalledWith("a");
    expect(filesApi.list).toHaveBeenCalledWith("b");
  });

  it("refreshes tickets and KPIs after marking a ticket fixed", async () => {
    vi.spyOn(anomaliesApi, "setStatus").mockImplementation(async (_id, status) => {
      vi.mocked(anomaliesApi.list).mockImplementation(async (id) => [anomaly(id, id === "a" ? status : "open")]);
      return anomaly("a", status);
    });
    await render(<Redacteur />);
    const invalidate = vi.spyOn(client, "invalidateQueries");
    await click(container.querySelector("button[aria-expanded=false]"));
    const statusSelect = container.querySelector<HTMLSelectElement>(".red-status-select");
    expect(statusSelect).not.toBeNull();
    await act(async () => {
      if (statusSelect) {
        statusSelect.value = "fixed";
        statusSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    await settle();
    expect(anomaliesApi.setStatus).toHaveBeenCalledWith("ticket-a", "fixed", undefined);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["kpis"] });
    expect(client.getQueryData<AnomalyOut[]>(["anomalies", "a"])?.[0]?.status).toBe("fixed");
  });
});

describe("knowledge themes", () => {
  it("summarizes fixed tickets in one theme, collapses provenance and updates after a status change", async () => {
    vi.mocked(anomaliesApi.list).mockImplementation(async (id) => [anomaly(id, "fixed")]);
    await render(<Knowledge />);
    expect(container.querySelectorAll("article.card h2")).toHaveLength(1);
    expect(container.querySelector("article.card h2")?.textContent).toBe("Safety");
    expect([...container.querySelectorAll(".kpi-value")].map((node) => node.textContent)).toEqual(["2", "1", "2", "1"]);
    expect(container.querySelectorAll("li")).toHaveLength(1);
    expect(container.querySelector("button[aria-expanded=false]")).not.toBeNull();
    await click(container.querySelector("article.card button[aria-expanded=false]"));
    expect(container.querySelector("article.card button[aria-expanded=true]")).not.toBeNull();
    expect(container.textContent).toContain("Project a");
    expect(container.textContent).toContain("Project b");
    await act(async () => { client.setQueryData(["anomalies", "a"], [anomaly("a", "open")]); });
    await act(async () => { client.setQueryData(["anomalies", "b"], [anomaly("b", "open")]); });
    await settle();
    expect(container.querySelectorAll("article.card h2")).toHaveLength(0);
    expect([...container.querySelectorAll(".kpi-value")].map((node) => node.textContent)).toEqual(["0", "0", "0", "0"]);
    expect(container.textContent).toContain("knowledge.empty");
  });

  it("keeps capitalization totals stable when search filters the source details", async () => {
    vi.mocked(anomaliesApi.list).mockImplementation(async (id) => [anomaly(id, "fixed")]);
    await render(<Knowledge />);
    const input = container.querySelector("input");
    await act(async () => {
      if (input) {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "Warning a");
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    await settle();
    expect([...container.querySelectorAll(".kpi-value")].map((node) => node.textContent)).toEqual(["2", "1", "2", "1"]);
    expect(container.querySelectorAll("article.card article")).toHaveLength(1);
    await click([...container.querySelectorAll("button")].find((button) => button.textContent === "knowledge.growth"));
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect([...container.querySelectorAll("tbody td")].map((node) => node.textContent)).toEqual(["+2", "2"]);
  });

  it("keeps the connectivity diagram collapsed and exposes five focusable trigger descriptions", async () => {
    await render(<Knowledge />);
    const diagram = [...container.querySelectorAll("button")].find((button) => button.textContent === "connectivity.title");
    expect(diagram?.getAttribute("aria-expanded")).toBe("false");
    await click(diagram);
    expect(diagram?.getAttribute("aria-expanded")).toBe("true");
    expect(container.querySelectorAll("figure button[aria-label='connectivity.triggerLabel']")).toHaveLength(5);
    expect([...container.querySelectorAll(".connectivity-source")].map((node) => node.getAttribute("data-state"))).toEqual(["active", "inactive", "active", "inactive", "inactive"]);
  });

  it("reports failed status retrieval as unavailable, never as absent or connected", async () => {
    vi.mocked(healthApi.connectivity).mockRejectedValue(new Error("Synthetic connectivity unavailable"));
    await render(<Knowledge />);
    await click([...container.querySelectorAll("button")].find((button) => button.textContent === "connectivity.title"));
    const sources = container.querySelectorAll(".connectivity-source");
    expect(sources[2]?.getAttribute("data-state")).toBe("error");
    expect(sources[2]?.textContent).toContain("connectivity.unavailable");
  });

  it("counts only enabled validated rules and shows unconfigured folders as inactive", async () => {
    vi.mocked(settingsApi.rulesLegacy).mockResolvedValue({
      overridden: false,
      rules: { regles_personnalisees: [
        { label: "Active", consigne: "Synthetic check" },
        { label: "Disabled", consigne: "", enabled: false },
        { label: "Pending", consigne: "", validated: false },
      ] },
    });
    await render(<Knowledge />);
    expect(healthApi.connectivity).not.toHaveBeenCalled();
    await click([...container.querySelectorAll("button")].find((button) => button.textContent === "connectivity.title"));
    expect(container.querySelectorAll(".connectivity-source")[1]?.getAttribute("data-state")).toBe("inactive");
    expect(container.querySelectorAll(".connectivity-source")[4]?.getAttribute("data-state")).toBe("active");
  });

  it("reflects unavailable sources and the AI switch from a fresh connectivity probe", async () => {
    await render(<Knowledge />);
    await click([...container.querySelectorAll("button")].find((button) => button.textContent === "connectivity.title"));
    expect(container.querySelector(".connectivity-hub")?.textContent).toContain("connectivity.aiDisabled");
    const snapshot = await healthApi.connectivity();
    vi.mocked(healthApi.connectivity).mockResolvedValue({
      ...snapshot, ai_enabled: true, ai_connection: "unreachable",
      sources: { ...snapshot.sources, reference: { configured: 1, available: 0, unavailable: 1 } },
    });
    await click([...container.querySelectorAll("button")].find((button) => button.textContent === "connectivity.refresh"));
    expect(container.querySelectorAll(".connectivity-source")[2]?.getAttribute("data-state")).toBe("error");
    expect(container.querySelector(".connectivity-hub")?.textContent).toContain("connectivity.aiEnabled");
    expect(container.querySelector(".connectivity-hub")?.textContent).toContain("connectivity.ai.unreachable");
  });
});

describe("LLM settings disclosure", () => {
  it("starts collapsed without a key and can be expanded explicitly", async () => {
    vi.spyOn(settingsApi, "read").mockResolvedValue({
      api_key_set: false, api_key_preview: "", base_url: "", chat_model: "", embed_model: "",
      vision_model: "", llm_enabled: true, llm_tested: false,
    });
    await render(<MistralForm />);
    const toggle = container.querySelector("button[aria-controls='llm-settings-body']");
    expect(toggle?.getAttribute("aria-expanded")).toBe("false");
    expect(container.querySelector<HTMLElement>("#llm-settings-body")?.hidden).toBe(true);
    await click(toggle);
    expect(toggle?.getAttribute("aria-expanded")).toBe("true");
  });
});
