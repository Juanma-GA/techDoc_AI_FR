import { expect, test } from "@playwright/test";

test("switches between isolated histories and hides BREX profiles in demo mode", async ({ page }) => {
  let demoEnabled = false;
  const normalDocuments = [{
    id: "normal-document", filename: "normal-history.pdf", source_format: "pdf",
    s1000d_issue: "4.2", context_hint: "mixed", status: "extracted", dm_type: null,
    page_count: 1, has_xml: true, violation_count: 0, created_at: "2026-10-30T10:00:00Z",
  }];
  const demoDocuments = [{
    ...normalDocuments[0],
    id: "demo-document", filename: "demo-history.pdf",
  }];
  const normalProfile = {
    id: "normal-brex", name: "Normal BREX", s1000d_issue: "4.2",
    created_at: "2026-10-30T10:00:00Z",
  };
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/v1/settings") {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON() as { demo_enabled?: boolean };
        if (body.demo_enabled !== undefined) demoEnabled = body.demo_enabled;
      }
      await route.fulfill({
        json: {
          api_key_set: false, base_url: "", chat_model: "", embed_model: "",
          llm_enabled: false, demo_enabled: demoEnabled,
        },
      });
    } else if (path.endsWith("/health")) {
      await route.fulfill({ json: { status: "ok", version: "test", db: "ok", llm: "disabled" } });
    } else if (path === "/api/v1/documents") {
      await route.fulfill({ json: demoEnabled ? demoDocuments : normalDocuments });
    } else if (path === "/api/v1/brex") {
      await route.fulfill({ json: demoEnabled ? [] : [normalProfile] });
    } else if (path === "/api/v1/brex/normal-brex") {
      await route.fulfill({
        json: {
          ...normalProfile, dmc: "DMC-NORMAL", dm_code: {}, rules: [], unsupported_rules: [],
        },
      });
    } else if (path === "/api/v1/migration-inputs") {
      await route.fulfill({
        json: demoEnabled
          ? { issue: "4.2", context_hint: "mixed", brex_id: null, files: {} }
          : {
              issue: "4.2", context_hint: "mixed", brex_id: normalProfile.id,
              files: { document: { filename: "normal-input.pdf" } },
            },
      });
    } else if (path === "/api/v1/migration-inputs/document") {
      await route.fulfill({ contentType: "application/pdf", body: "Synthetic normal file." });
    } else if (path.endsWith("/settings/preliminary-rules")) {
      await route.fulfill({ json: { revision: 0, groups: [] } });
    } else if (path.endsWith("/admin/stats")) {
      await route.fulfill({
        json: { documents: 0, extracted: 0, brex_profiles: 0, total_size_bytes: 0 },
      });
    } else {
      await route.fulfill({ json: [] });
    }
  });

  await page.goto("/migration");
  await expect(page.getByText("normal-history.pdf")).toBeVisible();
  await expect(page.locator(".brex-profile-control")).toHaveCount(1);
  const issueSelect = page.getByLabel("Version S1000D");
  await expect(issueSelect).toHaveValue("4.2");
  const documentInput = page.locator('input[type="file"][accept=".pdf,.docx"]');
  await expect.poll(() => documentInput.evaluate((input: HTMLInputElement) => input.files?.[0]?.name))
    .toBe("normal-input.pdf");

  await page.getByRole("link", { name: "Paramètres", exact: true }).click();
  await page.getByRole("button", { name: "Mode démo", exact: true }).click();
  await page.getByRole("link", { name: "Migration", exact: true }).click();
  await expect(page.getByText("demo-history.pdf")).toBeVisible();
  await expect(page.getByText("normal-history.pdf")).toHaveCount(0);
  await expect(page.locator(".brex-profile-control")).toHaveCount(0);
  await expect(issueSelect).toHaveValue("4.1");
  await expect.poll(() => documentInput.evaluate((input: HTMLInputElement) => input.files?.[0]?.name))
    .toBe("WEG-WMO.pdf");

  await page.getByRole("link", { name: "Paramètres", exact: true }).click();
  await page.getByRole("button", { name: "Mode normal", exact: true }).click();
  await page.getByRole("link", { name: "Migration", exact: true }).click();
  await expect(page.getByText("normal-history.pdf")).toBeVisible();
  await expect(page.getByText("demo-history.pdf")).toHaveCount(0);
  await expect(page.locator(".brex-profile-control")).toHaveCount(1);
  await expect(issueSelect).toHaveValue("4.2");
  await expect.poll(() => documentInput.evaluate((input: HTMLInputElement) => input.files?.[0]?.name))
    .toBe("normal-input.pdf");
});
