import { test, expect } from "@playwright/test";

test.describe("FTM Agent v3 smoke", () => {
  test("loads the dashboard with sidebar nav", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/FTM Agent/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Tableau de bord|Dashboard/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Projets|Projects/i })).toBeVisible();
  });
});
