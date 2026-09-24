import { test, expect } from "@playwright/test";

test.describe("Doc Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Doc Reviewer/i)).toBeVisible();
  });

  test("shows the active client rules instead of the legacy checklist panel", async ({ page }) => {
    await page.goto("/rules");

    await expect(page.getByRole("heading", { name: "THALES" })).toBeVisible();
    await expect(page.getByText("CUSTOM_CMM_NUMBER", { exact: true })).toBeVisible();
    await expect(page.locator(".rules-table input[type=checkbox]")).toHaveCount(42);
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
