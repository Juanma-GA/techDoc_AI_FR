import { expect, test } from "@playwright/test";

test("root redirects to migration", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/migration$/);
  await expect(page.getByText(/Migration/)).toBeVisible();
});
