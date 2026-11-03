import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressBar } from "./ProgressBar";

describe("ProgressBar", () => {
  it("renders a labelled determinate progress value with tokenized track and fill", () => {
    render(<ProgressBar value={42} label="Document analysis" />);

    expect(screen.getByRole("status")).toHaveTextContent("Document analysis");
    expect(screen.getByRole("progressbar", { name: "Document analysis" })).toHaveAttribute(
      "aria-valuenow",
      "42",
    );
    expect(screen.getByRole("progressbar").firstElementChild).toHaveStyle({ width: "42%" });
    expect(screen.getByRole("progressbar").firstElementChild).toHaveClass("bg-brand");
    expect(screen.getByRole("progressbar")).toHaveClass("bg-bg-3");
  });

  it.each([
    [-10, "0"],
    [110, "100"],
  ])("clamps %i to the supported range", (value, expected) => {
    render(<ProgressBar value={value} label="Document analysis" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", expected);
    expect(screen.getByRole("progressbar").firstElementChild).toHaveStyle({
      width: `${expected}%`,
    });
  });

  it("rejects a non-finite value instead of displaying false progress", () => {
    expect(() => ProgressBar({ value: Number.NaN, label: "Document analysis" }))
      .toThrow("ProgressBar value must be a finite number.");
  });
});
