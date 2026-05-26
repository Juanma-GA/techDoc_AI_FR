import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MultiSelect } from "./MultiSelect";

const items = [
  { id: "a", label: "Doc A" },
  { id: "b", label: "Doc B" },
];

describe("MultiSelect", () => {
  it("shows the allLabel when value is empty", () => {
    render(
      <MultiSelect items={items} value={[]} onChange={() => {}} allLabel="Tous les docs" />,
    );
    expect(screen.getByText("Tous les docs")).toBeInTheDocument();
  });

  it("calls onChange when an item is clicked", async () => {
    const onChange = vi.fn();
    render(<MultiSelect items={items} value={[]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button"));
    const item = await screen.findByText("Doc A");
    await userEvent.click(item);
    expect(onChange).toHaveBeenCalledWith(["a"]);
  });

  it("shows count when multiple items are selected", () => {
    render(<MultiSelect items={items} value={["a", "b"]} onChange={() => {}} />);
    expect(screen.getByText("2 sélections")).toBeInTheDocument();
  });
});
