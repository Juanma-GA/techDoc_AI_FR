import { expect, test } from "@playwright/test";

test("home page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("TEMPLATE");
  await expect(page.locator(".ui-sidebar-version")).toHaveCount(0);
  await expect(page.getByText(/TEMPLATE/)).toBeVisible();
});
