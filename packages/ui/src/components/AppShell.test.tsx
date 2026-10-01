import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell, sidebarNavItemClass } from "./AppShell";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { LlmStatus } from "./LlmStatus";

const labels = {
  label: "LLM",
  title: "LLM status",
  on: "ON",
  off: "OFF",
  untested: "TO TEST",
  noKey: "NO KEY",
};

describe("AppShell", () => {
  it("renders the shared sidebar and normalizes the version prefix", () => {
    render(
      <AppShell
        title="Example"
        version="v2"
        navigation={<a className={sidebarNavItemClass(true)} href="/">Home</a>}
      >
        <p>Page content</p>
      </AppShell>,
    );

    expect(screen.getByText("Example")).toBeTruthy();
    expect(screen.getByText("v2")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeTruthy();
    expect(screen.getByText("Page content")).toBeTruthy();
  });

  it("marks the selected language and reports changes", () => {
    const onLanguageChange = vi.fn();
    render(
      <LanguageSwitcher
        languages={["fr", "en"]}
        currentLanguage="fr"
        onLanguageChange={onLanguageChange}
      />,
    );

    expect(screen.getByRole("button", { name: "FR" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(onLanguageChange).toHaveBeenCalledWith("en");
  });

  it("keeps the disabled LLM state neutral", () => {
    render(<LlmStatus status="disabled" labels={labels} />);

    expect(screen.getByText("OFF").getAttribute("data-status")).toBe("disabled");
  });
});