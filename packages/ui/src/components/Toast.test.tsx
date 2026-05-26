import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  Toast,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  Toaster,
} from "./Toast";

describe("Toast", () => {
  it("renders title and description when open", () => {
    render(
      <ToastProvider>
        <Toast open>
          <ToastTitle>Saved</ToastTitle>
          <ToastDescription>Your changes are persisted.</ToastDescription>
        </Toast>
        <Toaster />
      </ToastProvider>,
    );
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Your changes are persisted.")).toBeInTheDocument();
  });
});
