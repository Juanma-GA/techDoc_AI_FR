import { expect, test } from "@playwright/test";
import { mockWorkspace } from "./workspace-mock";

test.beforeEach(async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({ json: { demo_enabled: false } }),
  );
});

test("defaults to dark when there is no saved theme, even if the OS prefers light", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.addInitScript(() => localStorage.removeItem("theme"));
  await page.goto("/");

  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("respects an explicitly saved light theme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.addInitScript(() => localStorage.setItem("theme", "light"));
  await page.goto("/");

  await expect(page.locator("html")).not.toHaveClass(/dark/);
});
