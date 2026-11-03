import { expect, test } from "@playwright/test";

test("colorization selects local profiles by path without uploading files", async ({ page }) => {
  const selectedPath = "D:\\Demo\\Composer Profiles";
  let folderPickerCalls = 0;
  let localUploadCalls = 0;

  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/api/v1/tree-optimization/pick-folder") {
      folderPickerCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ path: selectedPath }),
      });
      return;
    }
    if (pathname === "/api/v1/browse/local-upload") {
      localUploadCalls += 1;
      await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
      return;
    }

    const responses: Record<string, unknown> = {
      "/api/v1/health": { status: "ok", version: "0.1.0", db: "ok" },
      "/api/v1/imports": [],
      "/api/v1/identification": [],
      "/api/v1/browse/roots": { input: "", output: "", detected: [] },
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

  await page.goto("/colorization");
  const profilesInput = page.getByRole("textbox", { name: /Dossier des profils Composer/ });
  await expect(profilesInput).toBeVisible();
  await page.getByRole("button", { name: "Parcourir" }).click();
  await expect(profilesInput).toHaveValue(selectedPath);

  expect(folderPickerCalls).toBe(1);
  expect(localUploadCalls).toBe(0);
});
