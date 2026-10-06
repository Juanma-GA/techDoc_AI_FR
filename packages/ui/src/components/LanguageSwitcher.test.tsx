import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "./LanguageSwitcher";

describe("LanguageSwitcher", () => {
  it("marks the current language as pressed and the others as not", () => {
    render(
      <LanguageSwitcher
        languages={["fr", "en"]}
        currentLanguage="fr"
        onLanguageChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "FR" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "EN" })).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onLanguageChange with the clicked language", async () => {
    const onLanguageChange = vi.fn();
    render(
      <LanguageSwitcher
        languages={["fr", "en"]}
        currentLanguage="fr"
        onLanguageChange={onLanguageChange}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(onLanguageChange).toHaveBeenCalledWith("en");
  });

  it("uses the caller's translated ariaLabel instead of the English default (L-12)", () => {
    render(
      <LanguageSwitcher
        languages={["fr", "en"]}
        currentLanguage="fr"
        onLanguageChange={() => {}}
        ariaLabel="Langue"
      />,
    );
    expect(screen.getByRole("group", { name: "Langue" })).toBeInTheDocument();
  });

  it("falls back to the English default ariaLabel when none is passed", () => {
    render(
      <LanguageSwitcher
        languages={["fr", "en"]}
        currentLanguage="fr"
        onLanguageChange={() => {}}
      />,
    );
    expect(screen.getByRole("group", { name: "Language" })).toBeInTheDocument();
  });
});
