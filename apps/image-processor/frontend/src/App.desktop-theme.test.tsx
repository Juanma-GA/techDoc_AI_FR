import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import i18n from "./i18n";
import { App } from "./App";
import { settingsApi } from "./lib/api";
import { mockWorkspaceApi } from "./test/workflow";

const setTheme = vi.fn().mockResolvedValue(undefined);

describe("desktop window theme", () => {
  beforeEach(() => {
    setTheme.mockClear();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((media: string) => ({
        matches: false,
        media,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    document.documentElement.classList.add("dark");
    vi.spyOn(settingsApi, "read").mockResolvedValue({ demo_enabled: false });
    mockWorkspaceApi();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete window.__TAURI__;
    document.documentElement.classList.remove("dark");
  });

  it("syncs the initial theme and subsequent app theme changes", async () => {
    window.__TAURI__ = {
      window: { getCurrentWindow: () => ({ setTheme }) },
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/settings"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(setTheme).toHaveBeenLastCalledWith("dark"));

    document.documentElement.classList.remove("dark");
    await waitFor(() => expect(setTheme).toHaveBeenLastCalledWith("light"));
  });

  it("uses shared navigation icons and a localized accessible collapse control", async () => {
    await i18n.changeLanguage("fr");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await screen.findByText("Sauvegarde locale à jour.");
    const detectionLink = screen.getByRole("link", { name: "Détection" });
    const historyLink = screen.getByRole("link", { name: "Historique" });
    expect(detectionLink.querySelector("svg")).toBeTruthy();
    expect(historyLink.querySelector("svg")).toBeTruthy();

    const collapseButton = screen.getByRole("button", { name: "Replier le menu" });
    expect(collapseButton.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(collapseButton);

    expect(screen.getByRole("button", { name: "Déplier le menu" }).getAttribute("aria-expanded"))
      .toBe("false");
    expect(screen.getByRole("link", { name: "Détection" })).toBeTruthy();

    await i18n.changeLanguage("en");
    expect(screen.getByRole("button", { name: "Expand menu" }).getAttribute("aria-expanded"))
      .toBe("false");
    await i18n.changeLanguage("fr");
  });
});
