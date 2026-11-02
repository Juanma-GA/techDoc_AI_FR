import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SelectMenu } from "./SelectMenu";

const options = [
  { value: "descriptive", label: "Descriptive" },
  { value: "procedural", label: "Procedural" },
  { value: "ipd", label: "Illustrated parts data" },
];

describe("SelectMenu", () => {
  it("opens a themed listbox and changes the selected value on click", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <SelectMenu
        label="DM type"
        value="descriptive"
        options={options}
        onValueChange={onValueChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "DM type" }));
    expect(screen.getByRole("listbox", { name: "DM type" })).toBeVisible();
    await user.click(screen.getByRole("option", { name: "Procedural" }));

    expect(onValueChange).toHaveBeenCalledWith("procedural");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("supports keyboard navigation and selection", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <SelectMenu
        label="DM type"
        value="descriptive"
        options={options}
        onValueChange={onValueChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "DM type" }));
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onValueChange).toHaveBeenCalledWith("procedural");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes on Escape without changing the selection", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <SelectMenu
        label="DM type"
        value="descriptive"
        options={options}
        onValueChange={onValueChange}
      />,
    );

    const trigger = screen.getByRole("button", { name: "DM type" });
    await user.click(trigger);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onValueChange).not.toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });
});
