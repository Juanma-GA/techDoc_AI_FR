import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormField } from "./FormField";
import { Input } from "./Input";

describe("FormField", () => {
  it("links the label and the hint to the control", () => {
    render(
      <FormField label="Base URL" hint="Mistral endpoint" id="base-url">
        <Input />
      </FormField>,
    );
    const input = screen.getByLabelText("Base URL");
    expect(input).toHaveAttribute("id", "base-url");
    expect(input).toHaveAttribute("aria-describedby", "base-url-hint");
    expect(screen.getByText("Mistral endpoint")).toHaveAttribute("id", "base-url-hint");
  });

  it("marks the control invalid and shows the error instead of the hint", () => {
    render(
      <FormField label="Key" hint="Never shared" error="Required" required>
        <Input />
      </FormField>,
    );
    const input = screen.getByLabelText(/Key/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-required", "true");
    expect(input).toHaveClass("border-danger");
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.queryByText("Never shared")).toBeNull();
  });
});
