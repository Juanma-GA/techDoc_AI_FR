import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders text content", () => {
    render(<Badge>open</Badge>);
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("applies the danger variant classes", () => {
    render(<Badge variant="danger">at risk</Badge>);
    expect(screen.getByText("at risk")).toHaveClass("text-danger");
  });

  it("falls back to the default variant", () => {
    render(<Badge>default</Badge>);
    expect(screen.getByText("default")).toHaveClass("text-fg-dim");
  });
});
