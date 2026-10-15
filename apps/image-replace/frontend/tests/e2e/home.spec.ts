import { expect, test } from "@playwright/test";

const imageData =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/GNcAAAAASUVORK5CYII=";

const ocrResult = {
  width: 2480,
  height: 3508,
  source_width: 1,
  source_height: 1,
  full_text: "R-001",
  lines: [
    {
      text: "R-001",
      confidence: 0.99,
      box: [[10, 10], [100, 10], [100, 30], [10, 30]],
      matched_references: ["R-001"],
    },
  ],
  references: [
    {
      reference: "R-001",
      found: true,
      line_indices: [0],
      replacement: "M-002",
      replacement_count: 1,
    },
  ],
  edited_image: imageData,
  filename: "ICN-01.jpg",
};

test("detection workflow uploads an image and displays OCR replacements", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({ json: { demo_enabled: false } }),
  );
  await page.route("**/api/v1/image-replace/ocr", (route) =>
    route.fulfill({ json: ocrResult }),
  );

  await page.goto("/");
  const navigation = page.getByRole("navigation");
  await expect(navigation.getByRole("link")).toHaveCount(2);
  await expect(navigation.getByRole("link", { name: "Paramètres" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Données" })).toHaveCount(0);

  const imageInput = page.locator('input[type="file"]').first();
  await imageInput.setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: Buffer.from(imageData.split(",")[1], "base64"),
  });
  await page.getByRole("button", { name: "Ajouter un couple" }).click();
  await page.getByRole("textbox", { name: "Référence à remplacer 1" }).fill("R-001");
  await page.getByRole("textbox", { name: "Nouveau repère 1" }).fill("M-002");
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();

  await expect(page.getByText("Références", { exact: true })).toBeVisible();
  await expect(page.getByText("ICN-01.jpg")).toBeVisible();
  await expect(page.getByText("M-002", { exact: true })).toBeVisible();
});

test("Excel upload exposes sheet, columns, and part selection", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({ json: { demo_enabled: false } }),
  );
  await page.route("**/api/v1/image-replace/excel/sheets", (route) =>
    route.fulfill({ json: { sheets: ["Repères"] } }),
  );
  await page.route("**/api/v1/image-replace/excel/columns", (route) =>
    route.fulfill({
      json: {
        columns: [
          { index: 1, letter: "A", header: "Référence", label: "A — Référence" },
          { index: 2, letter: "B", header: "Contenu", label: "B — Contenu" },
          { index: 3, letter: "C", header: "Repère", label: "C — Repère" },
          { index: 4, letter: "D", header: "ICN", label: "D — ICN" },
          { index: 5, letter: "E", header: "Pièce", label: "E — Pièce" },
        ],
      },
    }),
  );
  await page.route("**/api/v1/image-replace/excel/pieces", (route) =>
    route.fulfill({ json: { pieces: [{ row: 2, name: "Pompe A" }] } }),
  );

  await page.goto("/");
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: Buffer.from(imageData.split(",")[1], "base64"),
  });
  await page.locator('input[type="file"]').nth(1).setInputFiles({
    name: "mapping.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from("synthetic workbook"),
  });

  await page.getByLabel("Onglet").selectOption("Repères");
  await page.getByLabel("Noms des pièces").selectOption("5");
  await expect(page.getByLabel("Pièce à traiter")).toContainText("Pompe A");
  await page.getByLabel("Références à remplacer").selectOption("1");
  await page.getByLabel("Nouveaux repères").selectOption("3");
  await page.getByLabel("ICN (nom du JPG)").selectOption("4");
  await page.getByLabel("Pièce à traiter").selectOption("2");
  await expect(page.getByRole("button", { name: "Lancer l’OCR sur CPU" })).toBeEnabled();
});
