import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import i18n from "../i18n";
import { Home } from "./Home";

describe("Image Replace home workflow", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("fr");
  });

  it("starts with OCR disabled until an image is selected", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Détection et remplacement" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lancer l’OCR sur CPU" })).toBeDisabled();
  });

  it("adds and removes manual replacement pairs accessibly", async () => {
    const user = userEvent.setup();
    render(<Home />);

    await user.click(screen.getByRole("button", { name: "Ajouter un couple" }));
    expect(screen.getByRole("textbox", { name: "Référence à remplacer 1" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nouveau repère 1" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Supprimer le couple 1" }));
    expect(screen.queryByRole("textbox", { name: "Référence à remplacer 1" })).not.toBeInTheDocument();
  });
});
