import { expect, test } from "@playwright/test";

test("ECM Automation workspace renders", async ({ page }) => {
  await page.route("**/api/v1/ecm-automation/paths", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body:
        route.request().method() === "PUT"
          ? (route.request().postData() ?? "{}")
          : JSON.stringify({ source_path: "", tracker_path: "", output_path: "" }),
    }),
  );
  await page.route("**/api/v1/ecm-automation/browse", (route) => {
    const selections: Record<string, string[]> = {
      source_files: ["C:\\ECM\\ECN-A.pdf", "C:\\ECM\\ECN-B.pdf"],
      source_directory: ["C:\\ECM\\à traiter"],
      tracker_file: ["C:\\ECM\\tracker.xlsx"],
      output_directory: ["C:\\ECM\\sortie"],
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ paths: selections[route.request().postDataJSON().kind as string] ?? [] }),
    });
  });
  let analyzedSourcePath = "";
  let analyzedFolderMode = "";
  await page.route("**/api/v1/ecm-automation/preview", async (route) => {
    analyzedSourcePath = route.request().postDataJSON().source_path as string;
    analyzedFolderMode = route.request().postDataJSON().folder_mode as string;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source_path: analyzedSourcePath,
        tracker_path: "C:\\ECM\\tracker.xlsx",
        sheet_names: ["ECM Tracker"],
        sheet_name: "ECM Tracker",
        header_row: 1,
        columns: [
          { name: "Reference", index: 0, field: "reference" },
          { name: "Revision", index: 1, field: "revision" },
          { name: "Subject", index: 2, field: "subject" },
        ],
        records: [
          {
            source_path: "C:\\ECM\\ECN-A.pdf",
            file_name: "ECN-A.pdf",
            reference: "ECN-42",
            revision: "A",
            subject: "Cooling unit",
            tracker_values: ["ECN-42", "A", "Cooling unit"],
          },
          {
            source_path: "C:\\ECM\\ECN-B.pdf",
            file_name: "ECN-B.pdf",
            reference: "ECN-44",
            revision: "B",
            subject: "Actuator update",
            tracker_values: ["ECN-44", "B", "Actuator update"],
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/ecm-automation/folders", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        created_folders: [
          "C:\\ECM\\sortie\\ECN-42-A-Cooling unit",
          "C:\\ECM\\sortie\\ECN-44-B-Actuator update",
        ],
        existing_folders: [],
      }),
    }),
  );
  await page.route("**/api/v1/ecm-automation/tracker", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tracker_path: "C:\\ECM\\tracker.xlsx",
        rows_written: 2,
      }),
    }),
  );
  await page.goto("/");
  const renameExistingFolders = page.getByRole("checkbox", {
    name: /Renommer des dossiers existants|Rename existing folders/,
  });
  await expect(renameExistingFolders).not.toBeChecked();
  await expect(
    page.getByRole("img", { name: /Aide sur le mode de traitement des dossiers|Help for folder processing mode/ }),
  ).toHaveAttribute("title", /Cochez cette option|Check this when/);
  await renameExistingFolders.check();
  await expect(
    page.getByRole("textbox", { name: /Dossier parent des dossiers à renommer|Parent folder of existing folders/ }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Dossier de sortie|Output folder/ })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /Sélectionner le dossier parent|Select the parent folder/ }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: /Sélectionner le dossier parent|Select the parent folder/ }).click();
  await expect(
    page.getByRole("textbox", { name: /Dossier parent des dossiers à renommer|Parent folder of existing folders/ }),
  ).toHaveValue("C:\\ECM\\à traiter");
  await page.getByRole("button", { name: /Sélectionner le tracker Excel|Select the Excel tracker/ }).click();
  await page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ }).click();
  await expect(page.getByRole("heading", { name: /Prévisualisation et corrections|Preview and corrections/ })).toBeVisible();
  expect(analyzedFolderMode).toBe("rename");
  await renameExistingFolders.uncheck();
  await expect(page.getByRole("complementary").getByText("ECM Automation", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Données|Data/ })).toHaveCount(0);
  await expect(
    page.getByText(/Extraction limitée au texte sélectionnable|Extraction reads selectable PDF text only/),
  ).toHaveCount(0);
  const sourceField = page.getByRole("textbox", {
    name: /PDF ou dossier contenant les PDF|PDF or folder containing PDFs/,
  });
  await expect(page.getByRole("button", { name: /Sélectionner un ou plusieurs PDF|Select one or more PDFs/ })).toHaveCount(1);
  await expect(page.getByRole("button", { name: /Sélectionner un dossier source|Select a source folder/ })).toHaveCount(0);
  await page.getByRole("button", { name: /Sélectionner un ou plusieurs PDF|Select one or more PDFs/ }).click();
  await expect(sourceField).toHaveValue(/2 PDF sélectionnés|2 PDFs selected/);
  await page.getByRole("button", { name: /Sélectionner le tracker Excel|Select the Excel tracker/ }).click();
  await expect(page.getByRole("textbox", { name: /Tracker Excel|Excel tracker/ })).toHaveValue(
    "C:\\ECM\\tracker.xlsx",
  );
  await page.getByRole("button", { name: /Sélectionner le dossier de sortie|Select the output folder/ }).click();
  await expect(page.getByRole("textbox", { name: /Dossier de sortie|Output folder/ })).toHaveValue(
    "C:\\ECM\\sortie",
  );
  await page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ }).click();
  expect(analyzedSourcePath).toBe("C:\\ECM\\ECN-A.pdf\nC:\\ECM\\ECN-B.pdf");
  await expect(page.getByRole("heading", { name: /Prévisualisation et corrections|Preview and corrections/ })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Référence|Reference/ }).first()).toHaveValue("ECN-42");
  await expect(page.getByRole("textbox", { name: /Révision|Revision/ }).first()).toHaveValue("A");
  await expect(page.getByRole("textbox", { name: /Sujet|Subject/ }).first()).toHaveValue("Cooling unit");
  await page.getByRole("button", { name: /Créer les dossiers|Create folders/ }).click();
  await expect(page.getByRole("button", { name: /Terminé|Done/ })).toBeDisabled();
  await expect(page.getByRole("heading", { name: /Résultat de l'opération|Operation result/ })).toBeVisible();
  await expect(page.getByText("C:\\ECM\\sortie\\ECN-42-A-Cooling unit", { exact: true })).toBeVisible();
  await expect(page.getByText("C:\\ECM\\sortie\\ECN-44-B-Actuator update", { exact: true })).toBeVisible();
  await expect(page.getByText("C:\\ECM\\tracker.xlsx", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: /Ajouter les lignes au tracker|Add rows to tracker/ }).click();
  await expect(page.getByRole("button", { name: /Ajouté|Added/ })).toBeDisabled();
  await expect(page.getByText("C:\\ECM\\tracker.xlsx", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: /Référence|Reference/ }).first().fill("ECN-43");
  await expect(page.getByRole("button", { name: /Ajouter les lignes au tracker|Add rows to tracker/ })).toBeEnabled();
  await page.getByRole("button", { name: /Ajouter les lignes au tracker|Add rows to tracker/ }).click();
  await expect(page.getByRole("button", { name: /Ajouté|Added/ })).toBeDisabled();

  await page.getByRole("button", { name: "EN", exact: true }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText(/LLM|Mistral/i)).toHaveCount(0);
  await page.getByRole("button", { name: "FR" }).click();
  await expect(page.getByRole("heading", { name: "Paramètres" })).toBeVisible();
  await expect(page.getByText(/LLM|Mistral/i)).toHaveCount(0);
  await page.getByRole("link", { name: "Accueil" }).click();
  await expect(page.getByRole("heading", { name: "Résultat de l'opération" })).toBeVisible();
});
