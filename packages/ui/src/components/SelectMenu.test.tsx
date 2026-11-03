import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
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

  it("forwards the form ref, blur event, and accessibility attributes", () => {
    const ref = createRef<HTMLButtonElement>();
    const onBlur = vi.fn();
    render(
      <>
        <SelectMenu
          ref={ref}
          name="issue"
          label="Issue"
          value="4.2"
          options={[{ value: "4.2", label: "Issue 4.2" }]}
          onValueChange={vi.fn()}
          onBlur={onBlur}
          aria-describedby="issue-help"
          aria-required="true"
          aria-invalid="true"
        />
        <span id="issue-help">Choose an issue</span>
      </>,
    );

    const trigger = screen.getByRole("button", { name: "Issue" });
    expect(ref.current).toBe(trigger);
    expect(trigger).toHaveAttribute("aria-describedby", "issue-help");
    expect(trigger).toHaveAttribute("aria-required", "true");
    expect(trigger).toHaveAttribute("aria-invalid", "true");
    expect(document.querySelector<HTMLInputElement>('input[name="issue"]')?.value).toBe("4.2");
    fireEvent.blur(trigger);
    expect(onBlur).toHaveBeenCalledOnce();
  });
});
