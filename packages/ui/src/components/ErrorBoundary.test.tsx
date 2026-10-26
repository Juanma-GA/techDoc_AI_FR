import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

afterEach(() => {
  vi.restoreAllMocks();
});

function BrokenContent() {
  throw new Error("synthetic render failure");
}

describe("ErrorBoundary", () => {
  it("renders the shared fallback when a child throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BrokenContent />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "Application Error" })).toBeTruthy();
    expect(screen.getByText(/unexpected error occurred/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh Page" })).toBeTruthy();
  });
});
