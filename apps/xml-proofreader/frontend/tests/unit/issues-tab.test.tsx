import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { IssuesTab } from "../../src/ui/comments/tabs/IssuesTab";
import { useStore } from "../../src/ui/store";
import type { Issue } from "../../src/core/issues/types";

const BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><taskbody><context><p>Apply 2.5 lbf pressure before service.</p></context></taskbody></task>
`;

function issue(over: Partial<Issue> = {}): Issue {
  return {
    id: "i1", source: "proofreader", severity: "warning", message: "Mixed units.",
    quote: "Apply 2.5 lbf pressure", suggestion: "Apply 11 N pressure", ...over,
  };
}

describe("IssuesTab — D6 Accept gating", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "t.dita", BUF);
  });

  it("enables Accept when the quote is localizable and a suggestion exists", () => {
    useStore.getState().setIssues([issue()]);
    render(<IssuesTab />);
    const accept = screen.getByRole("button", { name: /Accept/ });
    expect(accept).toBeEnabled();
  });

  // G2 (ADR-0032): button is always enabled if there is a suggestion;
  // a quote that cannot be located shows an "approximate" title (not disabled).
  it("enables Accept with approximate title when the quote cannot be located (G2)", () => {
    useStore.getState().setIssues([issue({ quote: "text that is absent" })]);
    render(<IssuesTab />);
    const accept = screen.getByRole("button", { name: /Accept/ });
    expect(accept).toBeEnabled();
    expect(accept).toHaveAttribute("title", expect.stringMatching(/approximate/i));
  });

  it("shows no Accept button when there is no suggestion", () => {
    useStore.getState().setIssues([issue({ suggestion: undefined })]);
    render(<IssuesTab />);
    expect(screen.queryByRole("button", { name: /Accept/ })).toBeNull();
  });
});
