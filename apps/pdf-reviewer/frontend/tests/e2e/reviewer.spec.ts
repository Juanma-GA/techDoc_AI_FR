import { test, expect } from "@playwright/test";

test.describe("PDF Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/PDF Reviewer/i)).toBeVisible();
  });
});
