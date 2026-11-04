import { notifyManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { App } from "./App";
import { chatApi, demoSettingsApi, healthApi, projectsApi } from "./lib/api";
import { useChatStore } from "./stores/useChatStore";
import { useUnsavedGuardStore } from "./stores/useUnsavedGuardStore";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
}));
vi.mock("./i18n", () => ({ setAppLanguage: vi.fn() }));
vi.mock("./routes/Knowledge", () => ({
  Knowledge: () => <input aria-label="Page draft" defaultValue="Keep my edits" />,
}));
vi.mock("./routes/Manager", () => ({ Manager: () => <h1>Dashboard</h1> }));

let root: Root;
let container: HTMLDivElement;
let client: QueryClient;

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

async function settle() {
  await vi.waitFor(async () => {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
    expect(document.querySelector('[aria-label="chatbot.open"]')).not.toBeNull();
    expect(client.isFetching()).toBe(0);
  });
}

async function click(label: string) {
  const button = document.querySelector<HTMLButtonElement>(`[aria-label="${label}"]`);
  expect(button).not.toBeNull();
  await act(async () => button?.click());
  await settle();
}

async function render(path = "/knowledge") {
  await act(async () => root.render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Location /><App />
      </MemoryRouter>
    </QueryClientProvider>,
  ));
  await settle();
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("matchMedia", vi.fn((media: string) => ({
    matches: false, media, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
  notifyManager.setNotifyFunction((callback) => { act(callback); });
  useChatStore.getState().reset();
  useUnsavedGuardStore.getState().setGuard(null);
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(demoSettingsApi, "read").mockResolvedValue({ demo_enabled: true });
  vi.spyOn(healthApi, "read").mockResolvedValue({ status: "ok", db: "ok", version: "", llm: "disabled" });
  vi.spyOn(projectsApi, "list").mockResolvedValue([]);
  vi.spyOn(chatApi, "sessions").mockResolvedValue([]);
});

afterEach(async () => {
  await act(async () => root.unmount());
  client.clear();
  container.remove();
  useUnsavedGuardStore.getState().setGuard(null);
  vi.restoreAllMocks();
  notifyManager.setNotifyFunction((callback) => callback());
  vi.unstubAllGlobals();
});

it("opens a panel without navigating or clearing unsaved edits", async () => {
  await render();
  const trigger = document.querySelector('[aria-label="chatbot.open"]');
  expect(trigger?.textContent).toBe("");
  expect(trigger?.getAttribute("title")).toBe("chatbot.open");
  expect(trigger?.querySelector("svg")).not.toBeNull();
  const draft = document.querySelector('[aria-label="Page draft"]');
  await act(async () => useUnsavedGuardStore.getState().setGuard("Unsaved work"));
  await click("chatbot.open");
  await vi.waitFor(() => expect(document.querySelector("textarea")).not.toBeNull());
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  expect(document.querySelector('[data-testid="location"]')?.textContent).toBe("/knowledge");
  expect(document.querySelector('[aria-label="Page draft"]')).toBe(draft);
  expect(useUnsavedGuardStore.getState().message).toBe("Unsaved work");
  expect(document.querySelector('[aria-label="nav.leaveWithoutSaving"]')).toBeNull();
});

it("keeps the conversation and draft after closing and reopening", async () => {
  await render();
  await click("chatbot.open");
  await act(async () => {
    useChatStore.getState().setDraft("Synthetic unsent question");
    useChatStore.getState().pushUser("Synthetic conversation");
  });
  await click("chatbot.close");
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  await click("chatbot.open");
  await vi.waitFor(() => expect(document.querySelector("textarea")?.value).toBe("Synthetic unsent question"));
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Synthetic conversation");
});

it("closes with Escape and returns focus to the floating trigger", async () => {
  await render();
  await click("chatbot.open");
  await act(async () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  });
  await vi.waitFor(() => expect(document.querySelector('[role="dialog"]')).toBeNull());
  await vi.waitFor(() => expect(document.activeElement?.getAttribute("aria-label")).toBe("chatbot.open"));
});

it("opens old chatbot links as a panel over the dashboard", async () => {
  await render("/chatbot");
  await vi.waitFor(() => expect(document.querySelector('[role="dialog"]')).not.toBeNull());
  expect(document.querySelector('[data-testid="location"]')?.textContent).toBe("/");
  expect(container.textContent).toContain("Dashboard");
});

it.each([false, true])("hides the Data tab and redirects old links with demo=%s", async (demoEnabled) => {
  vi.mocked(demoSettingsApi.read).mockResolvedValue({ demo_enabled: demoEnabled });
  await render("/data");
  await vi.waitFor(() => expect(document.querySelector('[data-testid="location"]')?.textContent).toBe("/"));
  expect(container.querySelector('a[href="/data"]')).toBeNull();
  expect(container.textContent).toContain("Dashboard");
});
