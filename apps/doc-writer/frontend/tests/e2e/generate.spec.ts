import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      json: {
        enabled: false,
        authenticated: false,
        email: null,
        display_name: null,
        role: null,
        disabled_reason: null,
      },
    }),
  );
});

test("application shell renders with sidebar nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/doc-writer/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /Generate|Génération/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Documents/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Sessions/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Settings|Paramètres/i })).toBeVisible();
});

test("can navigate to Documents page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Documents/i }).click();
  await expect(page).toHaveURL(/documents/);
});
