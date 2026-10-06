import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

// L-12: AppShell renders its own ThemeToggle internally — a consuming app's
// i18next instance has no way to translate that label unless AppShell
// forwards it. Without `themeToggleLabel`, every POC shipped an
// English-only aria-label regardless of the app's current locale.
describe("AppShell", () => {
  it("forwards themeToggleLabel to the embedded ThemeToggle", () => {
    render(
      <AppShell title="App" navigation={null} themeToggleLabel="Changer de theme">
        content
      </AppShell>,
    );
    expect(screen.getByRole("button", { name: "Changer de theme" })).toBeInTheDocument();
  });

  it("falls back to the ThemeToggle default when no label is passed", () => {
    render(<AppShell title="App" navigation={null}>content</AppShell>);
    expect(screen.getByRole("button", { name: /switch to (dark|light) theme/i })).toBeInTheDocument();
  });
});
