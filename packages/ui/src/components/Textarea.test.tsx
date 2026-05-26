import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Textarea } from "./Textarea";

describe("Textarea", () => {
  it("renders with default rows attribute", () => {
    render(<Textarea data-testid="ta" />);
    expect(screen.getByTestId("ta")).toHaveAttribute("rows", "4");
  });

  it("accepts typed text", async () => {
    render(<Textarea placeholder="Brief" />);
    const ta = screen.getByPlaceholderText("Brief");
    await userEvent.type(ta, "Rédige une synthèse");
    expect(ta).toHaveValue("Rédige une synthèse");
  });

  it("applies error class when state=error", () => {
    render(<Textarea state="error" data-testid="ta" />);
    expect(screen.getByTestId("ta")).toHaveClass("border-danger");
  });
});
