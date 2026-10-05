import { expect, test } from "@playwright/test";

test("ECM Rename workspace renders", async ({ page }) => {
  await page.route("**/api/v1/ecm-rename/browse", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        path: {
          source_file: "C:\\ECM\\ECN.pdf",
          source_directory: "C:\\ECM\\à traiter",
          tracker_file: "C:\\ECM\\tracker.xlsx",
          output_directory: "C:\\ECM\\sortie",
        }[route.request().postDataJSON().kind as string] ?? null,
      }),
    }),
  );
  await page.route("**/api/v1/ecm-rename/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source_path: "C:\\ECM\\à traiter",
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
            source_path: "C:\\ECM\\à traiter\\ECN.pdf",
            file_name: "ECN.pdf",
            reference: "ECN-42",
            revision: "A",
            subject: "Cooling unit",
            tracker_values: ["ECN-42", "A", "Cooling unit"],
          },
        ],
      }),
    }),
  );
  await page.route("**/api/v1/ecm-rename/process", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        created_folders: ["C:\\ECM\\sortie\\ECN-42-A-Cooling unit"],
        tracker_path: "C:\\ECM\\tracker.xlsx",
        backup_path: "C:\\ECM\\Tracker_backup_20261005.xlsx",
        rows_written: 1,
      }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("complementary").getByText("ECM-rename", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Données|Data/ })).toHaveCount(0);
  await expect(
    page.getByText(/Extraction limitée au texte sélectionnable|Extraction reads selectable PDF text only/),
  ).toHaveCount(0);
  await page.getByRole("button", { name: /Sélectionner un PDF|Select a PDF/ }).click();
  await expect(
    page.getByRole("textbox", { name: /PDF ou dossier contenant les PDF|PDF or folder containing PDFs/ }),
  ).toHaveValue("C:\\ECM\\ECN.pdf");
  await page.getByRole("button", { name: /Sélectionner un dossier source|Select a source folder/ }).click();
  await expect(
    page.getByRole("textbox", { name: /PDF ou dossier contenant les PDF|PDF or folder containing PDFs/ }),
  ).toHaveValue("C:\\ECM\\à traiter");
  await page.getByRole("button", { name: /Sélectionner le tracker Excel|Select the Excel tracker/ }).click();
  await expect(page.getByRole("textbox", { name: /Tracker Excel|Excel tracker/ })).toHaveValue(
    "C:\\ECM\\tracker.xlsx",
  );
  await page.getByRole("button", { name: /Sélectionner le dossier de sortie|Select the output folder/ }).click();
  await expect(page.getByRole("textbox", { name: /Dossier de sortie|Output folder/ })).toHaveValue(
    "C:\\ECM\\sortie",
  );
  await page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ }).click();
  await expect(page.getByRole("heading", { name: /Prévisualisation et corrections|Preview and corrections/ })).toBeVisible();
  await page.getByRole("button", { name: /Créer les dossiers et mettre à jour le tracker|Create folders and update tracker/ }).click();
  await page.getByRole("button", { name: /Cliquer encore pour confirmer|Click again to confirm/ }).click();
  await expect(page.getByRole("heading", { name: /Résultat de l'opération|Operation result/ })).toBeVisible();
  await expect(page.getByText("C:\\ECM\\Tracker_backup_20261005.xlsx", { exact: true })).toBeVisible();
  await expect(page.getByText("C:\\ECM\\sortie\\ECN-42-A-Cooling unit", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "EN" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText(/LLM|Mistral/i)).toHaveCount(0);
  await page.getByRole("button", { name: "FR" }).click();
  await expect(page.getByRole("heading", { name: "Paramètres" })).toBeVisible();
  await expect(page.getByText(/LLM|Mistral/i)).toHaveCount(0);
  await page.getByRole("link", { name: "Accueil" }).click();
  await expect(page.getByRole("heading", { name: "Résultat de l'opération" })).toBeVisible();
});
