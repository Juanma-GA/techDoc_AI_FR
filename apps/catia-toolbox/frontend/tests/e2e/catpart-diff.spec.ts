import { expect, test } from "@playwright/test";

test("CATPart screening separates same GE identities and exports an Excel workbook", async ({ page }) => {
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
        status: "complete",
        old_count: 4,
        new_count: 4,
        matches: [
          {
            sin: "050N9",
            old_pns: ["9994M99P02"],
            new_pns: ["8888M88P02"],
            old_files: ["GE_050N9_9994M99P02_OLD.CATPart"],
            new_files: ["GE_050N9_8888M88P02_NEW.CATPart"],
          },
        ],
        same_ge: [
          {
            sin: "050N9",
            pn: "9994M99P01",
            old_files: ["GE_X-050N9-9994M99P01_OLD.CATPart"],
            new_files: ["GE-050N9-9994M99P01_NEW.CATPart"],
          },
        ],
        solo_a: [{ sin: "111A2", pn: "111PN", file: "GE_111A2_111PN_SOLO_A.CATPart" }],
        solo_b: [{ sin: "222B3", pn: "222PN", file: "GE_222B3_222PN_SOLO_B.CATPart" }],
        issues: [],
      },
    };
    if (pathname === "/api/v1/diff/catparts/export.xlsx") {
      await route.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        body: "synthetic workbook",
      });
      return;
    }
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
  await page.getByRole("button", { name: /CATPart screening|Écrémage CATPart/ }).click();

  const folderPaths = page.locator('input[type="text"]');
  await expect(folderPaths).toHaveCount(2);
  await folderPaths.nth(0).fill("older");
  await folderPaths.nth(1).fill("newer");
  await page.getByRole("button", { name: /Screen folders|Écrémer les dossiers/ }).click();

  await expect(page.getByText(/GE files with a shared SIN|GE à examiner/)).toBeVisible();
  await expect(page.getByText(/^SIN\s*:\s*050N9$/)).toHaveCount(1);
  await expect(page.getByText(/same SIN \+ PN|même SIN \+ PN/)).toBeVisible();
  await expect(page.getByText("GE_X-050N9-9994M99P01_OLD.CATPart")).toBeVisible();
  await expect(page.getByText(/solo A\s*:\s*1/i)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export Excel|Exporter le classeur Excel/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("catpart-ge-screening.xlsx");
});
