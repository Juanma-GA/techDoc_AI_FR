// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";

import fr from "../../locales/fr.json";
import en from "../../locales/en.json";
import { ProtectTool } from "./ProtectTool";

const mocks = vi.hoisted(() => ({
  chooseDestination: vi.fn(),
  processPDF: vi.fn(),
}));

vi.mock("../../shared/components/FileDropzone", () => ({
  FileDropzone: ({ onFiles }: { onFiles: (files: File[]) => void }) => (
    <button
      type="button"
      onClick={() =>
        onFiles([new File(["%PDF-synthetic"], "sample.pdf", { type: "application/pdf" })])
      }
    >
      Select a PDF
    </button>
  ),
}));
vi.mock("../../shared/api", () => ({
  chooseExportDestination: mocks.chooseDestination,
  processPDF: mocks.processPDF,
  validateExportFileName: () => null,
  formatOperationError: () => "Protection failed",
}));

async function setup(language: "fr" | "en" = "fr") {
  const i18n = createInstance();
  await i18n.init({
    lng: language,
    resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  render(
    <I18nextProvider i18n={i18n}>
      <ProtectTool />
    </I18nextProvider>,
  );
  fireEvent.click(screen.getByText("Select a PDF"));
  return {
    action: screen.getByRole("button", {
      name: language === "fr" ? "Protéger et télécharger" : "Protect and download",
    }),
    password: screen.getByLabelText(language === "fr" ? "Mot de passe d’ouverture" : "Open password"),
    confirmation: screen.getByLabelText(
      language === "fr" ? "Confirmer le mot de passe d’ouverture" : "Confirm open password",
    ),
    ownerPassword: screen.getByLabelText(
      language === "fr" ? "Mot de passe propriétaire" : "Owner password",
    ),
    language,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.chooseDestination.mockResolvedValue(undefined);
  mocks.processPDF.mockResolvedValue("protected.pdf");
});
afterEach(cleanup);

describe("ProtectTool", () => {
  it.each(["fr", "en"] as const)("encrypts the selected PDF with permissions (%s)", async (language) => {
    const form = await setup(language);
    fireEvent.change(form.password, { target: { value: "private-open-password" } });
    fireEvent.change(form.confirmation, { target: { value: "private-open-password" } });
    fireEvent.change(form.ownerPassword, { target: { value: "private-owner-password" } });
    fireEvent.click(form.action);

    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, filename] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("protect");
    expect(filename).toBe("protected.pdf");
    expect(data.get("user_password")).toBe("private-open-password");
    expect(data.get("owner_password")).toBe("private-owner-password");
    expect(data.get("allow_print")).toBe("true");
    expect(data.get("allow_copy")).toBe("false");
    expect(data.get("allow_modify")).toBe("false");
    expect(data.get("allow_comments")).toBe("true");
    expect(data.get("allow_form_fill")).toBe("true");
    expect(data.get("allow_sign")).toBe("true");
    expect((await screen.findByRole("status")).textContent).toContain(
      language === "fr"
        ? "Le fichier protégé protected.pdf a été téléchargé."
        : "Protected file protected.pdf has been downloaded.",
    );
    expect((form.password as HTMLInputElement).value).toBe("");
    expect((form.confirmation as HTMLInputElement).value).toBe("");
    expect((form.ownerPassword as HTMLInputElement).value).toBe("");
  });

  it("rejects mismatched passwords without sending them", async () => {
    const form = await setup();
    fireEvent.change(form.password, { target: { value: "private-open-password" } });
    fireEvent.change(form.confirmation, { target: { value: "another-open-password" } });
    fireEvent.change(form.ownerPassword, { target: { value: "private-owner-password" } });
    fireEvent.click(form.action);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Les deux saisies du mot de passe d’ouverture ne correspondent pas.",
    );
    expect(mocks.processPDF).not.toHaveBeenCalled();
  });

  it("allows disabling comments, form filling, and signing", async () => {
    const form = await setup();
    fireEvent.change(form.password, { target: { value: "private-open-password" } });
    fireEvent.change(form.confirmation, { target: { value: "private-open-password" } });
    fireEvent.change(form.ownerPassword, { target: { value: "private-owner-password" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Autoriser les commentaires et annotations" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Autoriser le remplissage des champs de formulaire" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Autoriser la signature des champs de formulaire" }));
    fireEvent.click(form.action);

    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const data = mocks.processPDF.mock.calls[0]?.[1] as FormData;
    expect(data.get("allow_comments")).toBe("false");
    expect(data.get("allow_form_fill")).toBe("false");
    expect(data.get("allow_sign")).toBe("false");
  });

  it("changes the open password using the owner password", async () => {
    await setup();
    fireEvent.click(screen.getByRole("button", { name: "Modifier le mot de passe d’ouverture" }));
    fireEvent.click(screen.getByText("Select a PDF"));
    fireEvent.change(screen.getByLabelText("Mot de passe propriétaire actuel"), {
      target: { value: "owner-password" },
    });
    fireEvent.change(screen.getByLabelText("Nouveau mot de passe d’ouverture"), {
      target: { value: "new-open-password" },
    });
    fireEvent.change(screen.getByLabelText("Confirmer le mot de passe d’ouverture"), {
      target: { value: "new-open-password" },
    });
    mocks.processPDF.mockResolvedValue("password-updated.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Modifier et télécharger" }));

    await waitFor(() => expect(mocks.processPDF).toHaveBeenCalledOnce());
    const [endpoint, data, filename] = mocks.processPDF.mock.calls[0] as [string, FormData, string];
    expect(endpoint).toBe("change-password");
    expect(filename).toBe("password-updated.pdf");
    expect(data.get("owner_password")).toBe("owner-password");
    expect(data.get("new_user_password")).toBe("new-open-password");
    expect(data.has("user_password")).toBe(false);
    expect((await screen.findByRole("status")).textContent).toContain(
      "Le mot de passe d’ouverture a été modifié dans password-updated.pdf.",
    );
  });
});
