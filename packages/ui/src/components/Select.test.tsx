import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Select } from "./Select";

const opts = [
  { value: "fr", label: "Francais" },
  { value: "en", label: "Anglais" },
  { value: "es", label: "Espagnol" },
];

describe("Select", () => {
  it("renders all provided options", () => {
    render(<Select options={opts} defaultValue="fr" data-testid="s" />);
    expect(screen.getByRole("option", { name: "Francais" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Anglais" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Espagnol" })).toBeInTheDocument();
  });

  it("fires onChange when user selects a new option", async () => {
    const onChange = vi.fn();
    render(
      <Select
        options={opts}
        defaultValue="fr"
        onChange={onChange}
        data-testid="s"
      />,
    );
    await userEvent.selectOptions(screen.getByTestId("s"), "en");
    expect(onChange).toHaveBeenCalled();
    expect(screen.getByTestId("s")).toHaveValue("en");
  });

  it("applies error state class when state=error", () => {
    render(<Select options={opts} state="error" data-testid="s" />);
    expect(screen.getByTestId("s")).toHaveClass("border-danger");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Select options={opts} disabled data-testid="s" />);
    expect(screen.getByTestId("s")).toBeDisabled();
  });
});
