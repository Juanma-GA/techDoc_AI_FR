import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("renders with placeholder and accepts typing", async () => {
    const onChange = vi.fn();
    render(<Input placeholder="Votre nom" onChange={onChange} />);
    const input = screen.getByPlaceholderText("Votre nom");
    await userEvent.type(input, "Alice");
    expect(onChange).toHaveBeenCalled();
    expect(input).toHaveValue("Alice");
  });

  it("applies error state class when state=error", () => {
    render(<Input state="error" data-testid="i" />);
    expect(screen.getByTestId("i")).toHaveClass("border-danger");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Input disabled data-testid="i" />);
    expect(screen.getByTestId("i")).toBeDisabled();
  });
});
