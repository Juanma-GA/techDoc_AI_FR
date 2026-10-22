import { fireEvent, render, screen } from "@testing-library/react";
import { Combine } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { AppShell, SidebarNavContent, sidebarNavItemClass } from "./AppShell";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { LlmStatus } from "./LlmStatus";

vi.mock("../hooks/useMediaQuery", () => ({
  useMediaQuery: () => false,
}));

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
        navigation={<a className={sidebarNavItemClass(true)} href="/">Home</a>}
      >
        <p>Page content</p>
      </AppShell>,
    );

    expect(screen.getByText("Example")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeTruthy();
    expect(screen.getByText("Page content")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeTruthy();
  });

  it("toggles the sidebar between expanded and icon-only states", () => {
    render(
      <AppShell
        title="Example"
        collapseLabel="Replier le menu"
        expandLabel="Déplier le menu"
        navigation={
          <a className={sidebarNavItemClass(true)} href="/" aria-label="Accueil">
            <SidebarNavContent icon="home" label="Accueil" />
          </a>
        }
      >
        <p>Page content</p>
      </AppShell>,
    );

    const sidebar = screen.getByRole("complementary");
    const collapseButton = screen.getByRole("button", { name: "Replier le menu" });
    expect(sidebar.getAttribute("data-collapsed")).toBe("false");
    expect(collapseButton.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(collapseButton);

    expect(sidebar.getAttribute("data-collapsed")).toBe("true");
    expect(screen.getByRole("button", { name: "Déplier le menu" }).getAttribute("aria-expanded")).toBe(
      "false",
    );
    expect(screen.getByRole("link", { name: "Accueil" })).toBeTruthy();
  });

  it("renders app-specific sidebar content with shared tab icons", () => {
    render(
      <AppShell
        title="Example"
        navigation={
          <a className={sidebarNavItemClass(false)} href="/" aria-label="Documents">
            <SidebarNavContent icon="files" label="Documents" />
          </a>
        }
        sidebarContent={<p>Document outline</p>}
      >
        <p>Page content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "Documents" }).querySelector("svg")).toBeTruthy();
    expect(screen.getByText("Document outline")).toBeTruthy();
    expect(screen.getByRole("complementary").getAttribute("data-has-content")).toBe("true");
  });

  it("renders a caller-provided Lucide icon inside the shared navigation content", () => {
    render(
      <a className={sidebarNavItemClass(false)} href="/" aria-label="Merge">
        <SidebarNavContent icon={Combine} label="Merge" />
      </a>,
    );

    expect(screen.getByRole("link", { name: "Merge" }).querySelector("svg")).toBeTruthy();
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
  it("forwards themeToggleLabel to the embedded ThemeToggle", () => {
    render(
      <AppShell title="App" navigation={null} themeToggleLabel="Changer de theme">
        content
      </AppShell>,
    );
    expect(screen.getByRole("button", { name: "Changer de theme" })).toBeTruthy();
  });

  it("falls back to the ThemeToggle default when no label is passed", () => {
    render(<AppShell title="App" navigation={null}>content</AppShell>);
    expect(screen.getByRole("button", { name: /switch to (dark|light) theme/i })).toBeTruthy();
  });
});
