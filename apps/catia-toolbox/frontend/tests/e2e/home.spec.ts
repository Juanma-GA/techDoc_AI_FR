import { expect, test } from "@playwright/test";

const settings = {
  onedrive_input_root: "",
  onedrive_output_root: "",
  composer_license_server: "",
  composer_converter_path: "",
  composer_settings_path: "",
};
const routes = ["/identification", "/diff", "/conversion", "/tree", "/colorization", "/smgxml-rename", "/settings", "/data"];

test.beforeEach(async ({ page }) => {
  let currentSettings = { ...settings };
  const nomenclatures = ["reference", "revision"].map((name, index) => ({
    id: `synthetic-nomenclature-${index}`,
    source_ref: `C:/synthetic/${name}-${"long-project-reference-".repeat(5)}.xlsm`,
    sheet: "Nomenclature",
    status: "completed",
    summary: { total: 2, to_treat: 1, mono_body: 1 },
    created_at: "2026-01-01T00:00:00Z",
  }));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (pathname === "/api/v1/settings") {
      if (request.method() === "POST") {
        currentSettings = { ...currentSettings, ...request.postDataJSON() };
      }
      await route.fulfill({ json: currentSettings });
      return;
    }
    if (/\/identification\/[^/]+\/items$/.test(pathname)) {
      await route.fulfill({ json: [] });
      return;
    }
    const responses: Record<string, unknown> = {
      "/api/v1/health": { status: "ok", version: "0.1.0", db: "ok" },
      "/api/v1/imports": [],
      "/api/v1/identification": nomenclatures,
      "/api/v1/browse/roots": { input: "", output: "", detected: [] },
      "/api/v1/browse/list": { scope: "input", root: "", path: "", entries: [] },
      "/api/v1/smgxml": [],
      "/api/v1/conversion/composer-status": {
        available: false, executable: "", settings_file: "", version: "", message: "Synthetic environment",
      },
      "/api/v1/admin/stats": {
        imports: 0, nodes: 0, diffs: 0, conversions: 0, colorizations: 0,
        nomenclatures: 2, smgxml_runs: 0, total_size_bytes: 0,
      },
    };
    if (pathname in responses) {
      await route.fulfill({ json: responses[pathname] });
    } else {
      await route.fulfill({ status: 404, json: { code: "SYNTHETIC_ROUTE_NOT_FOUND", message: pathname } });
    }
  });
});

test("navigation only exposes active modules", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/identification$/);
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator('nav a[href="/qc"], nav a[href="/checks"], nav a[href="/replacement"]')).toHaveCount(0);
  await expect(page.getByText(/Mistral|\bLLM\b|Intelligence artificielle/i)).toHaveCount(0);
});

test("retired routes redirect to identification", async ({ page }) => {
  for (const route of ["/qc", "/checks", "/replacement", "/missing-route"]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/identification$/);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  }
});

for (const width of [360, 768, 1280, 1920]) {
  test(`responsive layout at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      await page.goto(route);
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(main.getByTestId("route-loading")).toHaveCount(0);
      await expect(main.locator('svg[role="status"]')).toHaveCount(0);
      await expect.poll(() => main.evaluate((element) => element.scrollWidth - element.clientWidth), {
        message: `${route} overflows at ${width}px`,
      }).toBeLessThanOrEqual(1);
      const framedElements = await main.locator("section, .banner, .analysis-info, .kpi, .item-row, .file-browser, .identification-import-list")
        .evaluateAll((elements) => elements.filter((element) => {
          const style = getComputedStyle(element);
          return [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
            .some((value) => Number.parseFloat(value) > 0);
        }).map((element) => element.className));
      expect(framedElements, `${route} has decorative borders at ${width}px`).toEqual([]);
      if (width < 760) {
        expect(await main.evaluate((element) => element.clientHeight)).toBeGreaterThanOrEqual(900 * 0.75);
      }
    }
    await page.goto("/settings");
    await expect(page.locator("#od_input")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`settings-${width}.png`) });
    await expect(page.locator(".banner.warn")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await page.locator(".banner.warn").screenshot({ path: testInfo.outputPath(`warning-${width}.png`) });
  });
}

test("mobile navigation reaches every active module", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await page.goto("/");
  const navigation = page.getByRole("navigation").getByRole("combobox");
  for (const route of routes) {
    await navigation.selectOption(route);
    await expect(page).toHaveURL(new RegExp(`${route}$`));
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  }
  expect(await page.getByTestId("sidebar").evaluate((element) => element.getBoundingClientRect().width)).toBe(360);
});

test("local settings save without retired fields", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.locator("#od_input")).toBeVisible();
  await expect(page.getByText(/Mistral|\bLLM\b|Intelligence artificielle/i)).toHaveCount(0);
  await page.locator("#od_input").fill("C:/synthetic/input");
  const saved = page.waitForRequest((request) => request.url().endsWith("/api/v1/settings") && request.method() === "POST");
  await page.getByRole("button", { name: /Enregistrer|Save/ }).click();
  expect((await saved).postDataJSON()).toEqual({ ...settings, onedrive_input_root: "C:/synthetic/input" });
  await expect(page.getByRole("status").filter({ hasText: /enregistr|saved/i })).toBeVisible();
});

test("comparison tabs support keyboard navigation", async ({ page }) => {
  await page.goto("/diff");
  const nomenclatures = page.getByRole("tab", { name: /nomenclature/i });
  await nomenclatures.focus();
  await nomenclatures.press("ArrowRight");
  await expect(page.locator("#diff-tab-catparts")).toBeFocused();
  await expect(page.locator("#diff-tab-catparts")).toHaveAttribute("aria-selected", "true");
  await page.locator("#diff-tab-catparts").press("Home");
  await expect(page.locator("#diff-tab-folders")).toBeFocused();
  await expect(page.locator("#diff-tab-folders")).toHaveAttribute("aria-selected", "true");
});

test("settings reports failures and can retry", async ({ page }) => {
  let recovered = false;
  await page.route("**/api/v1/settings", async (route) => {
    await route.fulfill(recovered
      ? { json: settings }
      : { status: 503, json: { code: "SYNTHETIC_UNAVAILABLE", message: "Synthetic settings failure" } });
  });
  await page.goto("/settings");
  await expect(page.getByRole("alert")).toHaveText("Synthetic settings failure");
  await expect(page.getByRole("alert")).toHaveCSS("border-left-width", "0px");
  recovered = true;
  await page.getByRole("button", { name: /Réessayer|Retry/ }).click();
  await expect(page.locator("#od_input")).toBeVisible();
});

test("data reset still requires a second click", async ({ page }) => {
  let resets = 0;
  await page.route("**/api/v1/admin/reset/all", async (route) => {
    resets += 1;
    await route.fulfill({ json: { scope: "all", deleted: { nomenclature_runs: 2, local_upload_files: 0 } } });
  });
  await page.goto("/settings");
  await page.getByRole("button", { name: /^Tout supprimer$|^Delete all$/i }).click();
  expect(resets).toBe(0);
  await page.getByRole("button", { name: /Cliquer encore pour confirmer|Click again to confirm/ }).click();
  await expect.poll(() => resets).toBe(1);
  await expect(page.getByRole("status").filter({ hasText: /2/ })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /2/ })).toHaveCSS("border-left-width", "0px");
});

test("theme and language controls remain available", async ({ page }, testInfo) => {
  await page.goto("/settings");
  await expect(page.locator("#od_input")).toBeVisible();
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("Settings");
  await page.getByTestId("sidebar").getByRole("button", { name: /theme/i }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.screenshot({ path: testInfo.outputPath("settings-light-en.png") });
});
