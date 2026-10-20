import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import "./i18n";
import { App } from "./App";
import { settingsApi } from "./lib/api";

const setTheme = vi.fn().mockResolvedValue(undefined);

describe("desktop window theme", () => {
  beforeEach(() => {
    setTheme.mockClear();
    document.documentElement.classList.add("dark");
    window.__TAURI__ = {
      window: { getCurrentWindow: () => ({ setTheme }) },
    };
    vi.spyOn(settingsApi, "read").mockResolvedValue({
      api_key_set: false,
      base_url: "",
      chat_model: "",
      embed_model: "",
      llm_enabled: true,
      demo_enabled: false,
      llm_tested: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete window.__TAURI__;
    document.documentElement.classList.remove("dark");
  });

  it("syncs the initial theme and subsequent app theme changes", async () => {
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
});
