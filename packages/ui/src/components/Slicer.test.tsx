import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Slicer } from "./Slicer";

const items = [
  { id: "a", label: "Projet A" },
  { id: "b", label: "Projet B" },
];

describe("Slicer", () => {
  it("marks the 'all' pill active when value is empty", () => {
    render(<Slicer items={items} value={[]} onChange={() => {}} allLabel="Tous" />);
    expect(screen.getByRole("button", { name: "Tous" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("selects a project pill on click", async () => {
    const onChange = vi.fn();
    render(<Slicer items={items} value={[]} onChange={onChange} allLabel="Tous" />);
    await userEvent.click(screen.getByRole("button", { name: "Projet A" }));
    expect(onChange).toHaveBeenCalledWith(["a"]);
  });

  it("deselecting the last project falls back to 'all' ([])", async () => {
    const onChange = vi.fn();
    render(<Slicer items={items} value={["a"]} onChange={onChange} allLabel="Tous" />);
    await userEvent.click(screen.getByRole("button", { name: "Projet A" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
