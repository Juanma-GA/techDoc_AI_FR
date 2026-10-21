import { expect, test } from "@playwright/test";

test("desktop startup page shows the themed loading card", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.addInitScript(() => {
    localStorage.setItem("i18nextLng", "fr");
    localStorage.removeItem("theme");
  });
  await page.goto("/src/desktop-startup.html");

  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("heading", { name: "Image Processor" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Chargement…");
});
