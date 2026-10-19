import { test, expect } from "@playwright/test";

test.describe("Doc Reviewer smoke", () => {
  test("loads the documents list", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/Doc Reviewer/i)).toBeVisible();
  });

  test("shows the active client rules instead of the legacy checklist panel", async ({ page }) => {
    await page.route("**/api/v1/client-config", (route) =>
      route.fulfill({
        json: {
          client_code: "THALES",
          label: "THALES",
          bundle_version: "1.2.2",
          catalogs: [{ code: "THALES-CUSTOM", version: "v1" }],
          manifest_hash: "a1b2c3d4e5f6",
          mapping_hash: "a1b2c3d4e5f6",
        },
      }),
    );
    await page.route("**/api/v1/client-rules", (route) =>
      route.fulfill({
        json: [{
          code: "CUSTOM_CMM_NUMBER",
          name: "CMM number",
          description: "Check the CMM number",
          message: "CMM number mismatch",
          kind: "client",
          severity: "warning",
          execution: "deterministic",
          active: true,
          translations: {},
        }],
      }),
    );
    await page.goto("/rules");

    await expect(page.getByRole("heading", { name: "THALES" })).toBeVisible();
    await expect(page.getByText("Custom Cmm Number", { exact: true })).toBeVisible();
    await expect(page.locator(".rules-table input[type=checkbox]")).toHaveCount(1);
    await expect(page.getByText(/Checklist import/i)).toHaveCount(0);
  });

  test("keeps core routes within the viewport", async ({ page }) => {
    for (const path of ["/", "/documents", "/settings"]) {
      await page.goto(path);
      await expect(page.locator("main")).toBeVisible();

      const overflow = await page.evaluate(() => ({
        horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        body: document.body.scrollWidth - document.body.clientWidth,
      }));

      expect(overflow.horizontal).toBeLessThanOrEqual(1);
      expect(overflow.body).toBeLessThanOrEqual(1);
    }
  });

  test("uploads the configured demo PDF through the regular dashboard flow", async ({ page }) => {
    const settings = {
      api_key_set: false,
      api_key_preview: "",
      api_key_unreadable: false,
      base_url: "https://api.mistral.ai",
      chat_model: "mistral-small-latest",
      vision_model: "mistral-medium-3-5",
      vision_enabled: false,
      llm_enabled: true,
      llm_tested: false,
      checklist_ai_scan: false,
      demo_enabled: true,
    };
    let uploadBody = "";

    await page.route("**/api/v1/settings/mistral", (route) =>
      route.fulfill({ json: settings }),
    );
    await page.route("**/api/v1/health", (route) =>
      route.fulfill({
        json: { status: "ok", version: "test", db: "ok", llm: "disabled" },
      }),
    );
    await page.route("**/api/v1/documents**", async (route) => {
      if (route.request().method() === "POST") {
        uploadBody = route.request().postData() ?? "";
        await route.fulfill({ json: { id: "demo-document" } });
        return;
      }
      await route.fulfill({ json: [] });
    });
    await page.route("**/api/v1/suggestions", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/v1/client-rules", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/v1/client-config", (route) =>
      route.fulfill({
        json: {
          client_code: "THALES",
          label: "THALES",
          bundle_version: "test",
          catalogs: [],
          manifest_hash: "test",
          mapping_hash: "test",
        },
      }),
    );
    await page.route("**/demo/DEMO_CMM_PDF_anonyme.pdf", (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "application/pdf" },
        body: "%PDF-1.7 synthetic fixture",
      }),
    );

    await page.goto("/");

    await expect(page.getByText("MODE DÉMO", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Indicateurs clés" })).toBeVisible();
    await page.getByRole("button", { name: "Analyser un document" }).click();
    await page.waitForURL("**/documents/demo-document");

    expect(uploadBody).toContain('filename="DEMO_CMM_PDF_anonyme.pdf"');
  });
});
