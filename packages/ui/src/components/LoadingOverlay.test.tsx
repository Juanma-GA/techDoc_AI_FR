import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LoadingOverlay } from "./LoadingOverlay";

describe("LoadingOverlay", () => {
  it("renders nothing when not visible", () => {
    const { container } = render(<LoadingOverlay visible={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders with role=status and a polite live region when visible", () => {
    render(<LoadingOverlay visible label="Indexation…" />);
    const overlay = screen.getByRole("status");
    expect(overlay).toHaveAttribute("aria-live", "polite");
    expect(overlay).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Indexation…")).toBeInTheDocument();
  });
});
