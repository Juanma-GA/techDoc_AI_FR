import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const fr: typeof import("../../src/locales/fr.json") = JSON.parse(
  readFileSync(new URL("../../src/locales/fr.json", import.meta.url), "utf8"),
);

async function syntheticConversion(page: Page, generated = false) {
  const counts = { uploads: 0, downloads: 0, streams: 0, validations: 0, xml: 0, documents: generated ? 1 : 0 };
  const doc = { id: "synthetic-doc", filename: "synthetic.pdf", source_format: "pdf",
    status: generated ? "extracted" : "wizard", created_at: "2026-10-30T12:00:00Z" };
  const state = {
    step: generated ? "generate" : "split", split_level: "section",
    steps: ["split", "type", "structure", "generate"], has_brex_profile: false,
    resources: { dmrl_count: 0, has_cir: false, has_brex_rules: false, has_dm_header: false },
    dms: [{ dm_id: "synthetic-dm", title: "Synthetic section", dm_type: "descriptive", node_count: 1,
      has_xml: generated, xsd_valid: true, missing_fields: [], xsd_violations: [], brex_violations: [] }],
  };
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/settings/preliminary-rules")) await route.fulfill({ json: { revision: 0, groups: [] } });
    else if (path.endsWith("/settings")) await route.fulfill({ json: { demo_enabled: false } });
    else if (path.endsWith("/migration-inputs/document")) {
      counts.downloads += 1;
      await route.fulfill({ contentType: "application/pdf", body: "%PDF-1.7\nsynthetic-only" });
    } else if (path.endsWith("/migration-inputs")) await route.fulfill({ json: {
      issue: "4.2", context_hint: "mixed", brex_id: null,
      files: counts.documents ? { document: { filename: "synthetic.pdf" } } : {},
    } });
    else if (path === "/api/v1/documents") {
      if (route.request().method() === "POST") {
        counts.uploads += 1;
        const reused = counts.documents > 0;
        counts.documents = 1;
        await route.fulfill({ status: 201, json: doc, headers: reused ? { "X-Reused": "true" } : {} });
      } else await route.fulfill({ json: counts.documents ? [doc] : [] });
    } else if (path.endsWith("/pdf-cut/detect")) await route.fulfill({ json: {
      validation_required: false, selected_page: 1, selected_end_page: 1,
      default_start_page: 1, total_pages: 1, dmrl_titles: [], candidates: [],
    } });
    else if (path.endsWith("/wizard/start_stream")) {
      counts.streams += 1;
      await route.fulfill({ contentType: "text/event-stream", body:
        `event: session\ndata: {"document_id":"synthetic-doc"}\n\n` +
        `event: progress\ndata: {"step":"infer","pct":50}\n\n` +
        `event: done\ndata: ${JSON.stringify(state)}\n\n` });
    } else if (path.endsWith("/wizard/validate")) {
      counts.validations += 1;
      await route.fulfill({ json: { results: [{
        dm_id: "synthetic-dm", filename: "synthetic.xml", dmc: "DMC-SYNTHETIC",
        issue: "4.2", schema: "descript", status: "valid", error_count: 0, violations: [],
      }] } });
    } else if (path.includes("/wizard/dm/")) {
      counts.xml += 1;
      await route.fulfill({ contentType: "application/xml", body: "<dmodule/>" });
    } else if (path.endsWith("/wizard")) await route.fulfill({ json: state });
    else if (path.endsWith("/synthetic-doc")) await route.fulfill({ json: doc });
    else await route.fulfill({ json: [] });
  });
  return counts;
}

test("keeps inputs across navigation, reuses the upload and restores metadata without downloading", async ({ page }) => {
  const counts = await syntheticConversion(page);
  await page.goto("/migration");
  await page.locator('input[accept=".pdf,.docx"]').setInputFiles({
    name: "synthetic.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7\nsynthetic-only"),
  });
  await page.getByRole("link", { name: "Paramètres", exact: true }).click();
  await page.getByRole("link", { name: "Conversion S1000D", exact: true }).click();
  await expect(page.getByText(/synthetic\.pdf/).first()).toBeVisible();
  const start = page.getByRole("button", { name: fr.migration.upload.start, exact: true });
  await start.click();
  await expect(page).toHaveURL(/\/migration\/synthetic-doc$/);
  await expect(page.getByRole("button", { name: fr.migration.analysis.validate, exact: true })).toBeVisible();
  await start.click();
  await expect(page.getByText(fr.migration.ui.reused)).toBeVisible();
  expect(counts.uploads).toBe(1);
  expect(counts.streams).toBe(1);
  expect(counts.documents).toBe(1);
  await page.reload();
  await expect(page.getByText(/synthetic\.pdf/).first()).toBeVisible();
  expect(counts.downloads).toBe(0);
  await start.click();
  await expect(page.getByText(fr.migration.ui.reused)).toBeVisible();
  expect(counts.downloads).toBe(1);
  expect(counts.documents).toBe(1);
});

test("validates stored DMs without downloading XML and returns to the document URL", async ({ page }) => {
  const counts = await syntheticConversion(page, true);
  await page.goto("/migration/synthetic-doc");
  await page.getByRole("button", { name: fr.migration.generate.validate, exact: true }).click();
  await expect(page).toHaveURL(/\/validation$/);
  await expect(page.getByRole("heading", { name: "DMC-SYNTHETIC" })).toBeVisible();
  expect(counts.validations).toBe(1);
  expect(counts.xml).toBe(0);
  await page.getByRole("link", { name: fr.validation.backToConversion }).click();
  await expect(page).toHaveURL(/\/migration\/synthetic-doc$/);
});

test("imports 45 XML files in batches of 20 with at most two concurrent requests", async ({ page }) => {
  await syntheticConversion(page);
  const sizes: number[] = [];
  let active = 0;
  let maximum = 0;
  await page.route("**/api/v1/validation/dms", async (route) => {
    active += 1;
    maximum = Math.max(maximum, active);
    const names = [...(route.request().postData() ?? "").matchAll(/name="files"; filename="([^"]+)"/g)]
      .map((match) => match[1]!);
    sizes.push(names.length);
    await new Promise((resolve) => setTimeout(resolve, 50));
    active -= 1;
    await route.fulfill({ json: { results: names.map((filename) => ({
      filename, dmc: filename, issue: "4.2", schema: "descript", status: "valid",
      error_count: 0, violations: [],
    })) } });
  });
  await page.goto("/validation");
  await page.locator('.validation-import input[type="file"]').first().setInputFiles(
    Array.from({ length: 45 }, (_, index) => ({
      name: `synthetic-${index}.xml`, mimeType: "application/xml", buffer: Buffer.from("<dmodule/>"),
    })),
  );
  await expect(page.getByText("45/45 fichiers traités")).toBeVisible();
  expect(sizes).toEqual([20, 20, 5]);
  expect(maximum).toBe(2);
});
