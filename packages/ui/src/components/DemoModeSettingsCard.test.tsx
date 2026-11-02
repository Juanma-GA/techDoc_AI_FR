import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DemoModeSettingsCard } from "./DemoModeSettingsCard";

const labels = {
  title: "Operating mode",
  hint: "Normal by default.",
  normal: "Normal mode",
  demo: "Demo mode",
  saveError: "Could not save the mode.",
};

describe("DemoModeSettingsCard", () => {
  it("shows the current mode and reports changes", async () => {
    const onModeChange = vi.fn();
    render(<DemoModeSettingsCard mode="normal" labels={labels} onModeChange={onModeChange} />);
    expect(screen.getByRole("group", { name: "Operating mode" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Normal mode" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Demo mode" }));
    expect(onModeChange).toHaveBeenCalledWith("demo");
  });

  it("disables the selector and shows the save error", () => {
    render(<DemoModeSettingsCard mode="demo" labels={labels} onModeChange={() => {}} disabled error />);
    expect(screen.getByRole("button", { name: "Demo mode" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not save the mode.");
  });
});
