// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
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

    fireEvent.click(view.getByRole("button", { name: "Settings" }));
    fireEvent.click(view.getByRole("button", { name: "Demo mode" }));
    await waitFor(() => expect(view.getByText("DEMO MODE")).toBeTruthy());

    fireEvent.click(view.getByRole("button", { name: "Merge" }));
    await waitFor(() => {
      expect(view.getAllByText("DEMO_CMM_PDF_anonyme.pdf")).toHaveLength(2);
    });

    fireEvent.click(view.getByRole("button", { name: "Settings" }));
    fireEvent.click(view.getByRole("button", { name: "Normal mode" }));
    fireEvent.click(view.getByRole("button", { name: "Merge" }));

    await waitFor(() => {
      expect(view.queryAllByText("DEMO_CMM_PDF_anonyme.pdf")).toHaveLength(0);
    });
  });

  it("shows tools in visible categories separated by rules", async () => {
    const view = render(<App />);
    const navigation = view.getByRole("navigation", { name: "Main navigation" });
    const categories = [
      "Organize pages",
      "Edit and optimize",
      "Convert and extract",
      "Comment and sign",
      "Security",
    ];
    for (const category of categories) {
      expect(within(navigation).getByText(category)).toBeTruthy();
    }

    expect(navigation.querySelectorAll(".ui-nav-group")).toHaveLength(5);
    expect(navigation.querySelectorAll(".pdf-nav-section-title")).toHaveLength(5);
    expect(within(navigation).getByRole("button", { name: "Merge" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Crop" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "PDF → Images" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Comments" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Protect PDF" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Settings" })).toBeTruthy();
  });

  it("translates the category labels into French", async () => {
    await i18n.changeLanguage("fr");
    const view = render(<App />);

    expect(view.getByText("Organiser les pages")).toBeTruthy();
    expect(view.getByText("Modifier et optimiser")).toBeTruthy();
    expect(view.getByText("Convertir et extraire")).toBeTruthy();
    expect(view.getByText("Annoter et signer")).toBeTruthy();
    expect(view.getByText("Sécurité")).toBeTruthy();
  });
});
