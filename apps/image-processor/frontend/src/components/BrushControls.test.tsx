import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import i18n from "../i18n";
import { useImageEditor } from "../hooks/useImageEditor";
import { BrushControls } from "./BrushControls";

function BrushControlsHarness() {
  const editor = useImageEditor({
    imageFile: null,
    imageUrl: "",
    manuallyEdited: false,
    onImageEdited: () => {},
    onInpaintingChange: () => {},
    t: i18n.t,
  });
  return <BrushControls editor={editor} disabled={false} t={i18n.t} />;
}

beforeEach(async () => {
  await i18n.changeLanguage("fr");
});

afterEach(cleanup);

describe("brush controls", () => {
  it("shows the brush toggle state accessibly", () => {
    render(<BrushControlsHarness />);

    const enableButton = screen.getByRole("button", { name: "Activer le pinceau" });
    expect(enableButton).toHaveAttribute("aria-pressed", "false");
    expect(enableButton.querySelector("svg")).toBeInTheDocument();

    fireEvent.click(enableButton);

    const disableButton = screen.getByRole("button", { name: "Désactiver le pinceau" });
    expect(disableButton).toHaveAttribute("aria-pressed", "true");
    expect(disableButton.querySelector("svg")).toBeInTheDocument();
  });
});
