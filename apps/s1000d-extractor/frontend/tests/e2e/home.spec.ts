import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/settings")) await route.fulfill({ json: { demo_enabled: false } });
    else if (path.endsWith("/migration-inputs")) await route.fulfill({
      json: { issue: "4.2", context_hint: "mixed", brex_id: null, files: {} },
    });
    else await route.fulfill({ json: [] });
  });
});

test("root redirects to migration", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/migration$/);
  await expect(page.getByRole("heading", { name: "Conversion S1000D" })).toBeVisible();
});

test("validation route exposes the batch import workspace", async ({ page }) => {
  await page.goto("/validation");
  await expect(page.getByRole("heading", { name: /validation/i }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Importer des fichiers|Import files/i })).toBeVisible();
});

test("validation empty states align and the left panel accepts dropped XML", async ({ page }) => {
  await page.route("**/api/v1/validation/dms", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      results: [{
        filename: "dropped.xml",
        dmc: "DMC-DROPPED",
        issue: "4.1",
        schema: "descript",
        status: "valid",
        error_count: 0,
        violations: [],
      }],
    }),
  }));
  await page.goto("/validation");

  const leftEmpty = page.getByTestId("validation-empty-list");
  const rightEmpty = page.getByTestId("validation-empty-detail");
  const [leftBox, rightBox] = await Promise.all([leftEmpty.boundingBox(), rightEmpty.boundingBox()]);
  expect(leftBox).not.toBeNull();
  expect(rightBox).not.toBeNull();
  expect(
    Math.abs((leftBox!.y + leftBox!.height / 2) - (rightBox!.y + rightBox!.height / 2)),
    `empty-state centers differ: ${JSON.stringify({ leftBox, rightBox })}`,
  ).toBeLessThan(3);

  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["<dmodule />"], "dropped.xml", { type: "application/xml" }));
    return transfer;
  });
  await leftEmpty.dispatchEvent("drop", { dataTransfer });

  await expect(page.getByRole("heading", { name: "DMC-DROPPED" })).toBeVisible();
});

test("validation displays the result for an imported XML DM", async ({ page }) => {
  await page.route("**/api/v1/validation/dms", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      results: [
        {
          filename: "valid.xml",
          dmc: "DMC-TEST",
          issue: "4.1",
          schema: "descript",
          status: "valid",
          error_count: 0,
          violations: [],
        },
        {
          filename: "invalid.xml",
          dmc: "DMC-INVALID",
          issue: "4.2",
          schema: "proced",
          status: "invalid",
          error_count: 1,
          violations: [{
            severity: "error",
            rule: "XSD",
            message: "Unexpected element in content.",
            path: "/dmodule/content",
            line: 12,
          }],
        },
      ],
    }),
  }));
  await page.goto("/validation");
  await page.getByTestId("validation-import").locator('input[type="file"][accept*=".xml"]').first().setInputFiles([
    { name: "valid.xml", mimeType: "application/xml", buffer: Buffer.from("<dmodule />") },
    { name: "invalid.xml", mimeType: "application/xml", buffer: Buffer.from("<dmodule />") },
  ]);

  await expect(page.getByRole("heading", { name: "DMC-TEST" })).toBeVisible();
  await expect(page.getByText(/Le DM est valide\.|The DM is valid\./)).toBeVisible();

  const invalidRow = page.getByRole("row").filter({ hasText: "DMC-INVALID" });
  await invalidRow.getByRole("cell").first().click();
  await expect(page.getByRole("heading", { name: "DMC-INVALID" })).toBeVisible();
  await expect(page.getByText("Unexpected element in content.")).toBeVisible();

  const errorsOnly = page.getByRole("checkbox", { name: /DM avec erreurs uniquement|DMs with errors only/i });
  await errorsOnly.check();
  await expect(page.getByRole("row").filter({ hasText: "DMC-INVALID" })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "DMC-TEST" })).toHaveCount(0);
  await errorsOnly.uncheck();
  await expect(page.getByRole("row").filter({ hasText: "DMC-TEST" })).toBeVisible();
});
