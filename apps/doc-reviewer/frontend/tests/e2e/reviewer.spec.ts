import { test, expect } from "@playwright/test";

test.describe("Doc Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Doc Reviewer/i)).toBeVisible();
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
