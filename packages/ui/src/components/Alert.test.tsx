import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Alert } from "./Alert";

describe("Alert", () => {
  it("uses role=status for informational variants", () => {
    render(<Alert title="Heads up">Details</Alert>);
    const alert = screen.getByRole("status");
    expect(alert).toHaveTextContent("Heads up");
    expect(alert).toHaveTextContent("Details");
  });

  it("uses role=alert for danger and applies the variant classes", () => {
    render(<Alert variant="danger">Failure</Alert>);
    expect(screen.getByRole("alert")).toHaveClass("border-danger/30", "bg-danger/10");
  });

  it("can hide the icon", () => {
    const { container } = render(<Alert icon={null}>No icon</Alert>);
    expect(container.querySelector("svg")).toBeNull();
  });
});
