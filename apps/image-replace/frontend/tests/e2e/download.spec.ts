import { readFile } from "node:fs/promises";

import { expect, test, type Page } from "@playwright/test";

import { excelPreset, mockWorkspace, syntheticImages } from "./workspace-mock";

async function downloadJpeg(page: Page, expected: Buffer) {
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Télécharger", exact: true }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("ICN-TEST.jpg");
  const path = await download.path();
  if (!path) throw new Error("Synthetic JPEG download missing.");
  const contents = await readFile(path);
  expect(contents.subarray(0, 3)).toEqual(Buffer.from([255, 216, 255]));
  expect(contents).toEqual(expected);
  await expect(page.getByRole("button", { name: "Télécharger", exact: true })).toBeEnabled();
}

for (const mode of ["lama", "color"] as const) {
  test(`ICN names and real JPEG downloads survive ${mode} before/after OCR, history and undo`, async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
    const storage = await mockWorkspace(page, excelPreset);
    await page.route("**/image-replace/excel/pairs", (route) => route.fulfill({
      json: { pairs: [{ reference: "R-1", replacement: "N-1" }] },
    }));
    await page.goto("/");
    const [original, edited] = await syntheticImages(page);
    const jpegUrl = await page.evaluate(async (source) => {
      const image = new Image();
      image.src = source;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Synthetic canvas missing.");
      context.drawImage(image, 0, 0);
      return canvas.toDataURL("image/jpeg");
    }, edited);
    const jpeg = Buffer.from(jpegUrl.split(",")[1]!, "base64");
    const exports: Buffer[] = [];
    await page.route("**/image-replace/export", (route) => {
      exports.push(route.request().postDataBuffer() ?? Buffer.alloc(0));
      return route.fulfill({
        body: jpeg, headers: {
          "Content-Type": "image/jpeg",
          "Content-Disposition": "attachment; filename*=UTF-8''ICN-TEST.jpg",
        },
      });
    });
    await page.route("**/image-replace/inpaint", (route) => route.fulfill({
      json: { edited_image: edited },
    }));
    await page.route("**/image-replace/ocr", (route) => route.fulfill({ json: {
      width: 100, height: 80, source_width: 100, source_height: 80,
      full_text: "", lines: [], references: [], edited_image: edited, filename: "ICN-TEST.jpg",
    } }));
    await page.locator('input[accept^="image/"]').setInputFiles({
      name: "not-the-icn.png", mimeType: "image/png", buffer: Buffer.from(original.split(",")[1]!, "base64"),
    });
    await page.getByLabel("Pièce à traiter").selectOption("2");
    await expect(page.getByRole("button", { name: "Activer le pinceau" })).toBeEnabled();

    async function brush() {
      await page.getByRole("button", { name: "Activer le pinceau" }).click();
      await page.getByLabel("Mode d’effacement").selectOption(mode);
      await page.getByLabel("Masque des zones à effacer").click({ position: { x: 45, y: 40 } });
      await page.getByRole("button", {
        name: mode === "lama" ? "Effacer avec LaMa" : "Remplir avec la couleur locale", exact: true,
      }).click();
      await expect(page.getByRole("button", { name: "Télécharger", exact: true })).toBeEnabled();
    }

    await brush();
    const preview = page.locator('img[draggable="false"]');
    const beforeOcr = await preview.getAttribute("src");
    if (!beforeOcr) throw new Error("Synthetic brush result missing.");
    await downloadJpeg(page, jpeg);
    expect(exports[0]?.includes(Buffer.from(beforeOcr.split(",")[1]!, "base64"))).toBe(true);
    expect(exports[0]?.toString()).toContain('name="excel_icn_column"');
    expect(exports[0]?.toString()).toContain('name="excel_piece_row"');
    await expect(preview).toHaveAttribute("src", beforeOcr);

    await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
    await expect(preview).toHaveAttribute("src", edited);
    await brush();
    const afterOcr = await preview.getAttribute("src");
    if (!afterOcr) throw new Error("Synthetic brush result missing.");
    await downloadJpeg(page, jpeg);
    expect(exports[1]?.includes(Buffer.from(afterOcr.split(",")[1]!, "base64"))).toBe(true);
    await expect.poll(() => storage.entries.values().next().value?.state.revisions.length).toBe(3);

    await page.getByRole("link", { name: "Historique", exact: true }).click();
    await expect(page.getByRole("heading", { name: "ICN-TEST.jpg" })).toBeVisible();
    await page.getByRole("button", { name: "Reprendre", exact: true }).click();
    await expect(preview).toHaveAttribute("src", afterOcr);
    await downloadJpeg(page, jpeg);
    await page.getByRole("button", { name: "Annuler la dernière modification" }).click();
    await expect(preview).toHaveAttribute("src", edited);
    await downloadJpeg(page, jpeg);
    await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
    await downloadJpeg(page, jpeg);
    expect(exports).toHaveLength(5);
  });
}

test("a failed JPEG export is visible and leaves the edited image unchanged", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await mockWorkspace(page);
  await page.goto("/");
  const [original] = await syntheticImages(page);
  await page.route("**/image-replace/ocr", (route) => route.fulfill({ json: {
    width: 100, height: 80, source_width: 100, source_height: 80,
    full_text: "", lines: [], references: [], edited_image: original, filename: "ICN-TEST.jpg",
  } }));
  await page.route("**/image-replace/export", (route) => route.fulfill({
    status: 500, json: { message: "Synthetic export failure." },
  }));
  await page.locator('input[accept^="image/"]').setInputFiles({
    name: "synthetic.png", mimeType: "image/png", buffer: Buffer.from(original.split(",")[1]!, "base64"),
  });
  await page.getByRole("button", { name: "Lancer l’OCR sur CPU" }).click();
  const preview = page.getByRole("img", { name: "Image résultante au format A4 portrait" });
  await expect(preview).toHaveAttribute("src", original);
  const downloads: string[] = [];
  page.on("download", (download) => downloads.push(download.suggestedFilename()));
  await page.getByRole("button", { name: "Télécharger", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Synthetic export failure.");
  await expect(preview).toHaveAttribute("src", original);
  expect(downloads).toEqual([]);
});
