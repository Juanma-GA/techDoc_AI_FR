import { test, expect } from "@playwright/test";

test.describe("Doc Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Doc Reviewer/i)).toBeVisible();
  });
});
