// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import i18n from "./i18n";

beforeEach(async () => {
  await i18n.changeLanguage("en");
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App demo mode", () => {
  it("preloads PDF tools and clears the sample when normal mode is restored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(new Blob(["%PDF-synthetic"]), { status: 200 })),
    );
    const view = render(<App />);

    fireEvent.click(view.getByRole("tab", { name: "Settings" }));
    fireEvent.click(view.getByRole("button", { name: "Demo mode" }));
    await waitFor(() => expect(view.getByText("DEMO MODE")).toBeTruthy());

    fireEvent.click(view.getByRole("tab", { name: "Merge" }));
    await waitFor(() => expect(view.getByText("DEMO_CMM_PDF_anonyme.pdf")).toBeTruthy());

    fireEvent.click(view.getByRole("tab", { name: "Settings" }));
    fireEvent.click(view.getByRole("button", { name: "Normal mode" }));
    fireEvent.click(view.getByRole("tab", { name: "Merge" }));

    await waitFor(() => {
      expect(view.queryByText("DEMO_CMM_PDF_anonyme.pdf")).toBeNull();
    });
  });
});
