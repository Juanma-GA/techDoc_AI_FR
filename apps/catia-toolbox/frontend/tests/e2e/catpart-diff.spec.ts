import { expect, test } from "@playwright/test";

test("CATPart folder comparison proposes a candidate for manual review", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const responses: Record<string, unknown> = {
      "/api/v1/health": {
        status: "ok",
        app_name: "Catia Toolbox",
        version: "0.1.0",
        llm: "disabled",
      },
      "/api/v1/imports": [],
      "/api/v1/identification": [],
      "/api/v1/browse/roots": { input: "", output: "", detected: [] },
      "/api/v1/diff/catparts": {
        status: "partial",
        old_count: 1,
        new_count: 1,
        exact_matches: [],
        candidates: [
          {
            old_file: "old.CATPart",
            new_file: "renamed.CATPart",
            similarity: 41.8,
            confidence: "low",
            old_geometry_quality: "partial",
            new_geometry_quality: "partial",
            binary_equal: false,
          },
        ],
        unmatched_old: [],
        unmatched_new: [],
        issues: [],
        reader: { available: true, required: true },
      },
    };
    const body = responses[pathname];
    if (body === undefined) {
      await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.goto("/");
  await page.getByRole("link", { name: /Compare|Comparaison/ }).click();
  await page.getByRole("button", { name: /CATIA parts|Pièces CATIA/ }).click();

  const folderPaths = page.locator('input[type="text"]');
  await expect(folderPaths).toHaveCount(2);
  await folderPaths.nth(0).fill("older");
  await folderPaths.nth(1).fill("newer");
  await page.getByRole("button", { name: /Analyze folders|Analyser les dossiers/ }).click();

  await expect(page.getByText(/Possible pairs to verify|Paires candidates à vérifier/)).toBeVisible();
  await page.getByRole("button", { name: /Confirm this pair|Confirmer cette paire/ }).click();
  await expect(page.getByText(/Pair manually confirmed|Paire confirmée manuellement/)).toBeVisible();
  await expect(page.getByText(/Different binary file|Fichier binaire différent/)).toBeVisible();
});
