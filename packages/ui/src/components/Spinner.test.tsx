import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Spinner } from "./Spinner";

describe("Spinner", () => {
  it("renders with default aria-label and role=status", () => {
    render(<Spinner />);
    const node = screen.getByRole("status");
    expect(node).toHaveAttribute("aria-label", "Chargement");
  });

  it("accepts custom aria-label", () => {
    render(<Spinner aria-label="Indexation en cours" />);
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      "Indexation en cours",
    );
  });
});
