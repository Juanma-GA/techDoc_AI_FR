import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LlmStatus, type LlmStatusLabels } from "./LlmStatus";

// L-13: maps the four health-check states from STANDARD_POC.md rule #13
// (ok/disabled/untested/not_configured) to their badge label and
// data-status, which drives the sidebar's green/orange/grey coloring.
const labels: LlmStatusLabels = {
  label: "LLM",
  title: "LLM status",
  on: "ON",
  off: "OFF",
  untested: "UNTESTED",
  noKey: "NO KEY",
};

describe("LlmStatus", () => {
  it.each([
    ["ok", "ON"],
    ["disabled", "OFF"],
    ["untested", "UNTESTED"],
    ["not_configured", "NO KEY"],
  ] as const)("renders %s as data-status=%s label", (status, expectedLabel) => {
    render(<LlmStatus status={status} labels={labels} />);
    const badge = screen.getByText(expectedLabel);
    expect(badge).toHaveAttribute("data-status", status);
  });

  it("falls back to an unknown badge for an unrecognized status string", () => {
    render(<LlmStatus status="something-else" labels={labels} />);
    const badge = screen.getByText("?");
    expect(badge).toHaveAttribute("data-status", "unknown");
  });

  it("falls back to an unknown badge when status is missing", () => {
    render(<LlmStatus labels={labels} />);
    const badge = screen.getByText("?");
    expect(badge).toHaveAttribute("data-status", "unknown");
  });

  it("renders the translated label and title", () => {
    render(<LlmStatus status="ok" labels={labels} />);
    expect(screen.getByText("LLM")).toBeInTheDocument();
    expect(screen.getByTitle("LLM status")).toBeInTheDocument();
  });
});
