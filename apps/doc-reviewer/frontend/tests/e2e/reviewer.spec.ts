import { test, expect } from "@playwright/test";

test.describe("Doc Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Doc Reviewer/i)).toBeVisible();
  });

  test("shows the active client rules instead of the legacy checklist panel", async ({ page }) => {
    await page.route("**/api/v1/client-config", (route) =>
      route.fulfill({
        json: {
          client_code: "THALES",
          label: "THALES",
          bundle_version: "1.2.2",
          catalogs: [{ code: "THALES-CUSTOM", version: "v1" }],
          manifest_hash: "a1b2c3d4e5f6",
          mapping_hash: "a1b2c3d4e5f6",
        },
      }),
    );
    await page.route("**/api/v1/client-rules", (route) =>
      route.fulfill({
        json: [{
          code: "CUSTOM_CMM_NUMBER",
          name: "CMM number",
          description: "Check the CMM number",
          message: "CMM number mismatch",
          kind: "client",
          severity: "warning",
          execution: "deterministic",
          active: true,
          translations: {},
        }],
      }),
    );
    await page.goto("/rules");

    await expect(page.getByRole("heading", { name: "THALES" })).toBeVisible();
    await expect(page.getByText("CUSTOM_CMM_NUMBER", { exact: true })).toBeVisible();
    await expect(page.locator(".rules-table input[type=checkbox]")).toHaveCount(1);
    await expect(page.getByText(/Checklist import/i)).toHaveCount(0);
  });

  test("keeps core routes within the viewport", async ({ page }) => {
    for (const path of ["/", "/documents", "/settings"]) {
      await page.goto(path);
      await expect(page.locator("main")).toBeVisible();

      const overflow = await page.evaluate(() => ({
        horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        body: document.body.scrollWidth - document.body.clientWidth,
      }));

      expect(overflow.horizontal).toBeLessThanOrEqual(1);
      expect(overflow.body).toBeLessThanOrEqual(1);
    }
  });
});
