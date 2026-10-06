import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Dialog, DialogContent, DialogTitle } from "./Dialog";

// L-12: the close button's aria-label was hardcoded "Close" with no prop to
// override it (unlike Toast's close button, which already forwarded props).
// A French-language POC had no way to translate it.
describe("DialogContent", () => {
  it("uses the translated closeLabel when provided", () => {
    render(
      <Dialog defaultOpen>
        <DialogContent closeLabel="Fermer">
          <DialogTitle>Titre</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: "Fermer" })).toBeInTheDocument();
  });

  it("falls back to the English default when no closeLabel is passed", () => {
    render(
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle>Title</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});
