import { expect, test } from "@playwright/test";

import { excelPreset, mockWorkspace, syntheticImages } from "./workspace-mock";

test("resumes selective OCR and brush edits, undo and full history, but starts home fresh", async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  const storage = await mockWorkspace(page, excelPreset);
  await page.route("**/image-replace/excel/pairs", (route) => route.fulfill({
    json: { pairs: [{ reference: "R-1", replacement: "N-1" }, { reference: "R-2", replacement: "N-2" }] },
  }));
  await page.goto("/");
  await expect(page.getByLabel("Pièce à traiter")).toHaveValue("");
  const [original, replaced, brushed] = await syntheticImages(page);
  const ocrImages: Buffer[] = [];
  const ocrPairs: string[] = [];
  await page.route("**/image-replace/ocr", (route) => {
    ocrImages.push(route.request().postDataBuffer() ?? Buffer.alloc(0));
    ocrPairs.push(route.request().postData() ?? "");
    return route.fulfill({ json: {
      width: 100, height: 80, source_width: 100, source_height: 80,
      full_text: "R-1 R-2", lines: [], references: [],
      edited_image: replaced, filename: "ICN-TEST.jpg",
    } });
  });
  const brushInputs: Buffer[] = [];
  await page.route("**/image-replace/inpaint", (route) => {
    brushInputs.push(route.request().postDataBuffer() ?? Buffer.alloc(0));
    return route.fulfill({ json: { edited_image: brushed } });
  });
  await page.locator('input[accept^="image/"]').setInputFiles({
    name: "synthetic.png", mimeType: "image/png", buffer: Buffer.from(original.split(",")[1]!, "base64"),
  });
  await page.getByLabel("Pièce à traiter").selectOption("2");
  await page.getByRole("checkbox", { name: "Appliquer le couple Excel 2", exact: true }).focus();
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
  const preview = page.getByRole("img", { name: "Image résultante au format A4 portrait" });
  await expect(preview).toHaveAttribute("src", replaced);
  expect(ocrPairs[0]).toContain(JSON.stringify([{ reference: "R-1", replacement: "N-1" }]));
  expect(ocrPairs[0]).not.toContain('"reference":"R-2"');

  await page.getByRole("button", { name: "Activer le pinceau" }).click();
  await page.getByLabel("Masque des zones à effacer").click({ position: { x: 45, y: 40 } });
  await page.getByRole("button", { name: "Effacer avec LaMa", exact: true }).click();
  await expect(preview).toHaveAttribute("src", brushed);
  expect(brushInputs[0]?.includes(Buffer.from(replaced.split(",")[1]!, "base64"))).toBe(true);
  await page.getByRole("checkbox", { name: "Appliquer le couple Excel 1", exact: true }).click();
  await page.getByRole("checkbox", { name: "Appliquer le couple Excel 2", exact: true }).click();
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
  await expect(preview).toHaveAttribute("src", replaced);
  expect(ocrImages[1]?.includes(Buffer.from(brushed.split(",")[1]!, "base64"))).toBe(true);
  expect(ocrPairs[1]).toContain(JSON.stringify([{ reference: "R-2", replacement: "N-2" }]));
  await page.getByRole("button", { name: "Annuler la dernière modification" }).click();
  await expect(preview).toHaveAttribute("src", brushed);
  await expect(page.getByText("Sauvegarde locale à jour.")).toBeVisible();
  await expect.poll(() => storage.entries.values().next().value?.state.revisions.length).toBe(2);
  expect(storage.getPreset()).not.toHaveProperty("pieceRow");
  expect(storage.getPreset()).not.toHaveProperty("image");

  await page.reload();
  await expect(page.getByText("synthetic.xlsx")).toBeVisible();
  await expect(page.getByLabel("Onglet")).toHaveValue("Parts");
  await expect(page.getByLabel("Noms des pièces")).toHaveValue("4");
  await expect(page.getByLabel("Pièce à traiter")).toHaveValue("");
  await expect(page.getByText("Choisir une image")).toBeVisible();
  await page.getByRole("link", { name: "Historique", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ICN-TEST.jpg" })).toBeVisible();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByLabel("Pièce à traiter")).toHaveValue("2");
  await expect(preview).toHaveAttribute("src", brushed);
  await expect(page.getByRole("checkbox", { name: "Appliquer le couple Excel 1", exact: true })).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Appliquer le couple Excel 2", exact: true })).toBeChecked();
  expect(ocrImages).toHaveLength(2);
  await expect(page.getByRole("heading", { name: "Opérations sur cette image" })).toBeVisible();
  await page.locator("html").evaluate((html) => html.classList.add("dark"));
  await page.screenshot({ path: info.outputPath("resumed-history.png"), fullPage: true });
  await page.getByRole("button", { name: "Annuler la dernière modification" }).click();
  await expect(preview).toHaveAttribute("src", replaced);
});

test("local-color brush becomes the next OCR source, in a narrow English light-theme view", async ({ page }, info) => {
  await page.addInitScript(() => {
    localStorage.setItem("i18nextLng", "en");
    localStorage.setItem("theme", "light");
  });
  await mockWorkspace(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator("html").evaluate((html) => html.classList.remove("dark"));
  await expect(page.locator("html")).not.toHaveClass(/\bdark\b/);
  const [original] = await syntheticImages(page);
  const requests: Buffer[] = [];
  await page.route("**/image-replace/ocr", (route) => {
    requests.push(route.request().postDataBuffer() ?? Buffer.alloc(0));
    return route.fulfill({ json: {
      width: 100, height: 80, source_width: 100, source_height: 80,
      full_text: "", lines: [], references: [], edited_image: original, filename: "result.png",
    } });
  });
  await page.locator('input[accept^="image/"]').setInputFiles({
    name: "synthetic.png", mimeType: "image/png", buffer: Buffer.from(original.split(",")[1]!, "base64"),
  });
  await page.getByRole("button", { name: "Enable brush" }).click();
  await page.getByLabel("Erase mode").selectOption("color");
  await page.getByLabel("Mask of areas to erase").click({ position: { x: 45, y: 40 } });
  await page.getByRole("button", { name: "Fill with local color", exact: true }).click();
  const edited = page.getByRole("img", { name: "Source image for PaddleOCR" });
  await expect(edited).not.toHaveAttribute("src", /^blob:/);
  const editedData = await edited.getAttribute("src");
  expect(editedData).toBeTruthy();
  await expect(page.getByRole("button", { name: "Run OCR on CPU" })).toBeEnabled();
  await page.screenshot({ path: info.outputPath("english-light-brush.png"), fullPage: true });
  await page.getByRole("button", { name: "Run OCR on CPU" }).click();
  await expect(page.getByRole("img", { name: "A4 portrait result image" })).toBeVisible();
  expect(requests[0]?.includes(Buffer.from(editedData!.split(",")[1]!, "base64"))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(page.getByRole("heading", { name: "History", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(page.getByRole("img", { name: "A4 portrait result image" })).toHaveAttribute("src", original);
});
