import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DemoModeBadge, DemoModeProvider, DemoModeSelector, useDemoMode } from "./DemoMode";

function ModeProbe() {
  const { mode, isReady } = useDemoMode();
  return <span>{isReady ? mode : "loading"}</span>;
}

describe("DemoMode", () => {
  it("provides the persisted mode to app routes", () => {
    render(
      <DemoModeProvider mode="demo" isReady>
        <ModeProbe />
      </DemoModeProvider>,
    );

    expect(screen.getByText("demo")).toBeInTheDocument();
  });

  it("exposes normal and demo choices as pressed states", () => {
    const onModeChange = vi.fn();
    render(
      <DemoModeSelector
        mode="normal"
        labels={{ normal: "Normal", demo: "Demo" }}
        ariaLabel="Operating mode"
        onModeChange={onModeChange}
      />,
    );

    expect(screen.getByRole("button", { name: "Normal" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Demo" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "Demo" }));
    expect(onModeChange).toHaveBeenCalledWith("demo");
  });

  it("shows a visible status badge only when demo mode is active", () => {
    const { rerender } = render(<DemoModeBadge label="DEMO MODE" visible={false} />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    rerender(<DemoModeBadge label="DEMO MODE" />);
    expect(screen.getByRole("status")).toHaveTextContent("DEMO MODE");
  });
});