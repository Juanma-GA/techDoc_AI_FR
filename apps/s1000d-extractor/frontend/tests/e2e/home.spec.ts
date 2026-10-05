import { expect, test } from "@playwright/test";

test("root redirects to migration", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/migration$/);
  await expect(page.getByRole("heading", { name: "Migration" })).toBeVisible();
});

test("validation route exposes the batch import workspace", async ({ page }) => {
  await page.goto("/validation");
  await expect(page.getByRole("heading", { name: /validation/i }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Importer des fichiers|Import files/i })).toBeVisible();
});

test("validation displays the result for an imported XML DM", async ({ page }) => {
  await page.route("**/api/v1/validation/dms", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      results: [{
        filename: "valid.xml",
        dmc: "DMC-TEST",
        issue: "4.1",
        schema: "descript",
        status: "valid",
        error_count: 0,
        violations: [],
      }],
    }),
  }));
  await page.goto("/validation");
  await page.locator('.validation-import input[type="file"][accept*=".xml"]').first().setInputFiles({
    name: "valid.xml",
    mimeType: "application/xml",
    buffer: Buffer.from("<dmodule />"),
  });

  await expect(page.getByRole("heading", { name: "DMC-TEST" })).toBeVisible();
  await expect(page.getByText(/Le DM est valide\.|The DM is valid\./)).toBeVisible();
});
