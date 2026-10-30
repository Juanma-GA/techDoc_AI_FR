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
          bundle_code: "thales_rules",
          bundle_label: "THALES",
          name: "CMM number",
          description: "Check the CMM number",
          message: "CMM number mismatch",
          rule_number: 1,
          kind: "client",
          scope: "verification",
          severity: "warning",
          execution: "deterministic",
          active: true,
          catalog_code: "THALES-CUSTOM",
          catalog_version: "v1",
          translations: {},
        }],
      }),
    );
    await page.goto("/rules");

    await expect(page.getByRole("heading", { name: "THALES" })).toBeVisible();
    await page.locator("details.collapsible > summary").click();
    await expect(page.getByText("Custom Cmm Number", { exact: true })).toBeVisible();
    await expect(page.locator(".rules-table input[type=checkbox]")).toHaveCount(1);
    await expect(page.getByText(/Checklist import/i)).toHaveCount(0);
  });

  test("keeps core routes within the viewport", async ({ page }) => {
    for (const viewport of [
      { width: 1280, height: 720 },
      { width: 1024, height: 768 },
    ]) {
      await page.setViewportSize(viewport);

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

  test("loads both real demo assets and submits them to the comparison API", async ({ page }, testInfo) => {
    let uploadBody = "";
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/settings/mistral") {
        await route.fulfill({ json: { demo_enabled: true, llm_enabled: false } });
      } else if (path === "/api/v1/health") {
        await route.fulfill({
          json: { status: "ok", version: "test", db: "ok", llm: "disabled" },
        });
      } else if (path === "/api/v1/comparisons" && route.request().method() === "POST") {
        uploadBody = route.request().postData() ?? "";
        await route.fulfill({
          status: 422,
          json: {
            code: "SYNTHETIC_SMOKE",
            message: "Synthetic comparison upload captured",
            detail: null,
            request_id: "smoke",
          },
        });
      } else {
        await route.fulfill({ json: [] });
      }
    });

    await page.goto("/comparison");

    const compare = page.getByRole("button", { name: "Comparer et enregistrer" });
    await expect(compare).toBeDisabled();
    const loadDemo = page.getByRole("button", { name: "Charger les deux PDF de démonstration" });
    await loadDemo.focus();
    await expect(loadDemo).toBeFocused();
    await page.keyboard.press("Enter");
    const reference = page.getByRole("combobox", { name: "Document de référence" });
    await expect(reference.locator("option")).toHaveCount(2);
    await expect(reference.locator("option:checked")).toHaveText("DEMO_CMM_PDF_anonyme.pdf");
    await expect(page.getByText("DEMO_CMM_PDF_revision_anonyme.pdf", { exact: true }).first()).toBeVisible();
    await expect(compare).toBeEnabled();
    expect(uploadBody).toBe("");

    for (const state of [
      { language: "FR", dark: true },
      { language: "FR", dark: false },
      { language: "EN", dark: false },
      { language: "EN", dark: true },
    ]) {
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.getByRole("button", { name: state.language, exact: true }).click();
      const isFrench = state.language === "FR";
      const demoLabel = isFrench ? "Charger les deux PDF de démonstration" : "Load both demo PDFs";
      await expect(page.getByRole("button", { name: demoLabel })).toBeVisible();
      const isDark = await page.locator("html").evaluate((root) => root.classList.contains("dark"));
      if (isDark !== state.dark) {
        await page.getByRole("button", { name: isFrench ? "Changer de thème" : "Switch theme" }).click();
      }
      if (state.dark) await expect(page.locator("html")).toHaveClass(/dark/);
      else await expect(page.locator("html")).not.toHaveClass(/dark/);

      await page.screenshot({
        path: testInfo.outputPath(`demo-${state.language}-${state.dark ? "dark" : "light"}.png`),
        fullPage: true,
      });
      for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
        await page.setViewportSize(viewport);
        expect(await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
        )).toBeLessThanOrEqual(1);
      }
    }

    await page.setViewportSize({ width: 1280, height: 720 });
    await page.getByRole("button", { name: "FR", exact: true }).click();
    await compare.click();
    await expect(page.getByRole("alert")).toContainText("Synthetic comparison upload captured");
    expect(uploadBody).toContain('filename="DEMO_CMM_PDF_anonyme.pdf"');
    expect(uploadBody).toContain('filename="DEMO_CMM_PDF_revision_anonyme.pdf"');
    expect(uploadBody).toContain('name="reference_index"\r\n\r\n0');
    expect(uploadBody.match(/%PDF-/g)).toHaveLength(2);
  });
});
