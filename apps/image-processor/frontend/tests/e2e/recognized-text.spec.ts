import { expect, test } from "@playwright/test";

import { mockWorkspace, syntheticImages } from "./workspace-mock";

test("replaces a recognized line in place on a narrow viewport", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  const storage = await mockWorkspace(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const [source, initial, edited] = await syntheticImages(page);
  let ocrRequestCount = 0;
  const lineReplacementRequests: string[] = [];
  await page.route("**/api/v1/image-processor/ocr", (route) => {
    ocrRequestCount += 1;
    return route.fulfill({ json: {
      width: 100,
      height: 80,
      source_width: 100,
      source_height: 80,
      full_text: "K555 A100",
      lines: [{
        text: "K555",
        confidence: 0.99,
        box: [[10, 10], [60, 10], [60, 28], [10, 28]],
        matched_references: [],
      }, {
        text: "A100",
        confidence: 0.98,
        box: [[10, 45], [60, 45], [60, 63], [10, 63]],
        matched_references: [],
      }],
      references: [],
      edited_image: initial,
      filename: "synthetic.jpg",
    } });
  });
  await page.route("**/api/v1/image-processor/replace-line", (route) => {
    const requestBody = route.request().postData() ?? "";
    lineReplacementRequests.push(requestBody);
    return route.fulfill({ json: {
      edited_image: requestBody.includes('name="replacement"\r\n\r\nA200') ? edited : initial,
      replacement_count: 1,
      replacement_font_size: 12,
    } });
  });

  await page.goto("/");
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: Buffer.from(source.split(",")[1]!, "base64"),
  });
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
  const secondBox = page
    .getByRole("group", { name: "Zones de texte reconnues" })
    .getByRole("button", { name: "Remplacer la ligne A100" });
  await secondBox.click();
  const replacementInput = page.getByRole("textbox", { name: "Nouveau texte pour A100" });
  await expect(replacementInput).toBeFocused();
  await page.screenshot({
    path: testInfo.outputPath("recognized-text-editor-mobile.png"),
    fullPage: true,
  });
  await replacementInput.fill("A200");
  await page.keyboard.press("Enter");

  const preview = page.getByRole("img", { name: "Image résultante au format A4 portrait" });
  await expect(preview).toHaveAttribute("src", edited);
  await expect(page.getByRole("textbox", { name: "Référence à remplacer 1" })).toHaveValue("A100");
  await expect(page.getByRole("textbox", { name: "Nouveau repère 1" })).toHaveValue("A200");
  await expect(page.getByText("Sauvegarde locale à jour.")).toBeVisible();
  expect(ocrRequestCount).toBe(1);
  expect(lineReplacementRequests[0]).toContain('name="reference"\r\n\r\nA100');
  expect(lineReplacementRequests[0]).toContain('name="replacement"\r\n\r\nA200');
  expect(lineReplacementRequests[0]).toContain('"text":"A100"');
  await expect.poll(
    () => storage.entries.values().next().value?.state.revisions.at(-1)?.kind,
  ).toBe("text-replacement");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("recognized-text-edit-mobile.png"),
    fullPage: true,
  });

  await page
    .getByRole("group", { name: "Zones de texte reconnues" })
    .getByRole("button", { name: "Modifier le remplacement de A100" })
    .click();
  await expect(replacementInput).toHaveValue("A200");
  await page.getByRole("button", { name: "Annuler cette modification" }).click();
  await expect(preview).toHaveAttribute("src", initial);
  await expect.poll(
    () => storage.entries.values().next().value?.state.revisions.length,
  ).toBe(3);
  expect(ocrRequestCount).toBe(1);
  expect(lineReplacementRequests).toHaveLength(2);
  expect(lineReplacementRequests[1]).toContain('name="replacement"\r\n\r\nA100');
  await expect(page.getByRole("textbox", { name: "Référence à remplacer 1" })).not.toBeVisible();

  await secondBox.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("textbox", { name: "Nouveau texte pour A100" })).toBeFocused();
});

test("undoes a box edit to its previous Excel/manual replacement", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await mockWorkspace(page);
  const [source, previousImage, editedImage] = await syntheticImages(page);
  let ocrRequestCount = 0;
  const lineReplacementRequests: string[] = [];
  await page.route("**/api/v1/image-processor/ocr", (route) => {
    ocrRequestCount += 1;
    return route.fulfill({ json: {
      width: 100,
      height: 80,
      source_width: 100,
      source_height: 80,
      full_text: "K555 A100",
      lines: [{
        text: "K555",
        confidence: 0.99,
        box: [[10, 10], [60, 10], [60, 28], [10, 28]],
        matched_references: [],
      }, {
        text: "A100",
        confidence: 0.98,
        box: [[10, 45], [60, 45], [60, 63], [10, 63]],
        matched_references: ["A100"],
      }],
      references: [{
        reference: "A100",
        found: true,
        line_indices: [1],
        replacement: "A150",
        replacement_count: 1,
      }],
      edited_image: previousImage,
      filename: "synthetic.jpg",
    } });
  });
  await page.route("**/api/v1/image-processor/replace-line", (route) => {
    const body = route.request().postData() ?? "";
    lineReplacementRequests.push(body);
    return route.fulfill({ json: {
      edited_image: body.includes('name="replacement"\r\n\r\nA200') ? editedImage : previousImage,
      replacement_count: 1,
      replacement_font_size: 12,
    } });
  });

  await page.goto("/");
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: Buffer.from(source.split(",")[1]!, "base64"),
  });
  await page.getByRole("button", { name: "Ajouter un couple" }).click();
  await page.getByRole("textbox", { name: "Référence à remplacer 1" }).fill("A100");
  await page.getByRole("textbox", { name: "Nouveau repère 1" }).fill("A150");
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();

  const textBoxes = page.getByRole("group", { name: "Zones de texte reconnues" });
  await textBoxes.getByRole("button", { name: "Modifier le remplacement de A100" }).click();
  const replacementInput = page.getByRole("textbox", { name: "Nouveau texte pour A100" });
  await expect(replacementInput).toHaveValue("A150");
  await replacementInput.fill("A200");
  await page.keyboard.press("Enter");
  const preview = page.getByRole("img", { name: "Image résultante au format A4 portrait" });
  await expect(preview).toHaveAttribute("src", editedImage);
  await expect(page.getByRole("textbox", { name: "Nouveau repère 1" })).toHaveValue("A200");

  await textBoxes.getByRole("button", { name: "Modifier le remplacement de A100" }).click();
  await page.getByRole("button", { name: "Annuler cette modification" }).click();
  await expect(preview).toHaveAttribute("src", previousImage);
  await expect(page.getByRole("textbox", { name: "Nouveau repère 1" })).toHaveValue("A150");
  expect(lineReplacementRequests).toHaveLength(2);
  expect(lineReplacementRequests[1]).toContain('name="replacement"\r\n\r\nA150');
  expect(ocrRequestCount).toBe(1);
});
