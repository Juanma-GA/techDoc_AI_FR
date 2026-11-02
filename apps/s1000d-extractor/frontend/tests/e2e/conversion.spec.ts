import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const fr: typeof import("../../src/locales/fr.json") = JSON.parse(
  readFileSync(new URL("../../src/locales/fr.json", import.meta.url), "utf8"),
);

function contrastRatio(foreground: string, background: string): number {
  const channels = (color: string) => {
    const values = color.match(/[\d.]+/g)?.slice(0, 3).map(Number);
    if (!values || values.length !== 3) throw new Error(`Unsupported computed color: ${color}`);
    return values.map((value) => {
      const channel = value / 255;
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
  };
  const luminance = (color: string) => {
    const [red, green, blue] = channels(color);
    return 0.2126 * red! + 0.7152 * green! + 0.0722 * blue!;
  };
  const first = luminance(foreground);
  const second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

async function syntheticConversion(page: Page, generated = false, unresolvedTypes = false) {
  const counts = { uploads: 0, downloads: 0, streams: 0, validations: 0, xml: 0, documents: generated ? 1 : 0 };
  const doc = { id: "synthetic-doc", filename: "synthetic.pdf", source_format: "pdf",
    status: generated ? "extracted" : "wizard", created_at: "2026-10-30T12:00:00Z" };
  const state = {
    step: unresolvedTypes ? "dmrl" : generated ? "generate" : "split", split_level: "section",
    steps: unresolvedTypes ? ["dmrl", "split", "generate"] : ["split", "type", "structure", "generate"],
    has_brex_profile: false,
    resources: { dmrl_count: 0, has_cir: false, has_brex_rules: false, has_dm_header: false },
    dms: [{ dm_id: "synthetic-dm", title: "Synthetic section", dm_type: "descriptive", node_count: 1,
      has_xml: generated, xsd_valid: true, missing_fields: [], xsd_violations: [], brex_violations: [] }],
    ...(unresolvedTypes ? {
      dmrl_dm_count: 1,
      dmrl: [{
        index: 0, arbo: "1", dmc: "DMC-SYNTHETIC", title: "Synthetic section",
        dm_type: "", dmrl_type: "", info_code: "999", info_code_schema: "unknown",
        info_code_dm_type: "", type_conflict: true, type_issue: "unsupported_schema",
        icn: "", is_pm_title: false, matched: true, match_rank: "exact", page: 1,
        matched_text: "Synthetic section",
      }],
    } : {}),
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
    } else if (path.endsWith("/wizard/update")) {
      const request = route.request().postDataJSON() as {
        op?: string; index?: number; dm_type?: string;
      };
      if (request.op === "set_type" && request.index != null && state.dmrl) {
        const row = state.dmrl[request.index];
        if (row && request.dm_type) row.dm_type = request.dm_type;
      }
      await route.fulfill({ json: state });
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

test("keeps the DMRL type picker legible and conflict notice padded in both themes", async ({ page }) => {
  await syntheticConversion(page, false, true);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/migration/synthetic-doc");
  const typeSelect = page.locator(".s1k-dm-type-select").first();
  await expect(typeSelect).toBeVisible();
  const notice = page.locator('div[role="alert"]').filter({ has: page.locator("details.space-y-3") });
  await expect(notice).toBeVisible();

  for (const theme of ["dark", "light"] as const) {
    await page.evaluate((value) => {
      document.documentElement.classList.toggle("dark", value === "dark");
    }, theme);
    const noticeStyles = await notice.evaluate((element) => ({
      paddingLeft: getComputedStyle(element).paddingLeft,
      paddingRight: getComputedStyle(element).paddingRight,
      lineHeight: getComputedStyle(element.querySelector("summary")!).lineHeight,
      listSpacing: getComputedStyle(element.querySelector("ul")!).marginTop,
    }));
    expect(Number.parseFloat(noticeStyles.paddingLeft)).toBeGreaterThanOrEqual(16);
    expect(noticeStyles.paddingLeft).toBe(noticeStyles.paddingRight);
    expect(Number.parseFloat(noticeStyles.lineHeight)).toBeGreaterThanOrEqual(20);
    expect(Number.parseFloat(noticeStyles.listSpacing)).toBeGreaterThan(0);
    await notice.screenshot({ path: `test-results/dmrl-type-notice-${theme}.png` });
  }

  await typeSelect.click();
  const listbox = page.getByRole("listbox").first();
  await expect(listbox).toBeVisible();
  for (const theme of ["dark", "light"] as const) {
    await page.evaluate((value) => {
      document.documentElement.classList.toggle("dark", value === "dark");
    }, theme);
    const optionColors = await listbox.getByRole("option").evaluateAll((options) =>
      options.map((option) => ({
        foreground: getComputedStyle(option).color,
        background: getComputedStyle(option).backgroundColor,
      })),
    );
    expect(optionColors).toHaveLength(4);
    for (const colors of optionColors) {
      expect(contrastRatio(colors.foreground, colors.background)).toBeGreaterThanOrEqual(4.5);
    }
    await listbox.screenshot({ path: `test-results/dmrl-type-picker-${theme}.png` });
  }

  await listbox.getByRole("option", { name: fr.dmType.descriptive }).click();
  await expect(typeSelect).toHaveText(fr.dmType.descriptive);
});

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
  await page.getByTestId("validation-import").locator('input[type="file"]').first().setInputFiles(
    Array.from({ length: 45 }, (_, index) => ({
      name: `synthetic-${index}.xml`, mimeType: "application/xml", buffer: Buffer.from("<dmodule/>"),
    })),
  );
  await expect(page.getByText("45/45 fichiers traités")).toBeVisible();
  expect(sizes).toEqual([20, 20, 5]);
  expect(maximum).toBe(2);
});
