import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CollapsibleSection } from "./CollapsibleSection";

describe("CollapsibleSection", () => {
  it("toggles its content with aria-expanded", async () => {
    render(
      <CollapsibleSection title="LLM" defaultOpen={false}>
        <p>Settings body</p>
      </CollapsibleSection>,
    );
    const toggle = screen.getByRole("button", { name: /LLM/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Settings body")).not.toBeVisible();

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Settings body")).toBeVisible();
    expect(document.getElementById(toggle.getAttribute("aria-controls") ?? "")).not.toBeNull();
  });

  it("supports controlled mode", async () => {
    const onOpenChange = vi.fn();
    render(
      <CollapsibleSection title="Advanced" open onOpenChange={onOpenChange}>
        <p>Body</p>
      </CollapsibleSection>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Advanced/ }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByRole("button", { name: /Advanced/ })).toHaveAttribute("aria-expanded", "true");
  });
});
