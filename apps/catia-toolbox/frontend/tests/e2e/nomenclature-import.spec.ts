import { expect, test, type Page } from "@playwright/test";

type Run = {
  id: string;
  source_ref: string;
  sheet: string;
  status: string;
  summary: { rows: number; detected_columns: string[] };
  created_at: string;
};

async function mockNomenclatures(page: Page) {
  const runs: Run[] = [];
  const previews: string[] = [];
  const analyses: string[] = [];
  let uploads = 0;
  let release: (() => void) | undefined;
  let delayed: "preview" | "analysis" | undefined;
  const pathFor = (index: number) => `C:\\synthetic\\upload-${index}\\nomenclature.xlsx`;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (pathname === "/api/v1/browse/local-upload") {
      uploads += 1;
      await route.fulfill({ json: {
        root: `C:\\synthetic\\upload-${uploads}`,
        files: [{ path: pathFor(uploads), rel: "nomenclature.xlsx", size: 20 }],
      } });
      return;
    }
    if (pathname === "/api/v1/identification/preview") {
      const { path } = request.postDataJSON() as { path: string };
      previews.push(path);
      if (delayed === "preview") {
        delayed = undefined;
        await new Promise<void>((resolve) => { release = resolve; });
      }
      const second = path === pathFor(2);
      await route.fulfill({ json: {
        sheet: "Nomenclature",
        sheets: ["Nomenclature", "Materiaux"],
        header_row_detected: 1,
        columns_map: second ? { sin: 0, designation: 1 } : { sin: 1, designation: 3 },
        rows: second
          ? [["SIN", "Designation"], ["SIN-B", "Preview B"]]
          : [["Other", "SIN", "Other 2", "Designation"], ["", "SIN-A", "", "Preview A"]],
      } });
      return;
    }
    if (pathname === "/api/v1/identification/nomenclature") {
      const { path } = request.postDataJSON() as { path: string };
      analyses.push(path);
      const run: Run = {
        id: `run-${runs.length + 1}`,
        source_ref: path,
        sheet: "Nomenclature",
        status: "completed",
        summary: { rows: 1, detected_columns: ["sin", "designation"] },
        created_at: "2026-01-01T00:00:00Z",
      };
      if (delayed === "analysis") {
        delayed = undefined;
        await new Promise<void>((resolve) => { release = resolve; });
      }
      runs.unshift(run);
      await route.fulfill({ json: run });
      return;
    }
    const run = runs.find((candidate) =>
      pathname === `/api/v1/identification/${candidate.id}/items`);
    if (run) {
      const items = [{
        id: `${run.id}-item`,
        sin: run.source_ref === pathFor(1) ? "RESULT-A" : "RESULT-B",
        designation: run.source_ref,
        mono_body: false,
      }];
      if (run.source_ref === pathFor(1)) {
        items.push({
          id: `${run.id}-duplicate`,
          sin: " result-a ",
          designation: "Synthetic duplicate",
          mono_body: false,
        });
        items.push({
          id: `${run.id}-unique`,
          sin: "RESULT-C",
          designation: "Synthetic unique",
          mono_body: false,
        });
      }
      const monoBodyFilter = new URL(request.url()).searchParams.get("mono_body");
      await route.fulfill({
        json: monoBodyFilter === "true" ? items.filter((item) => item.mono_body) : items,
      });
      return;
    }
    const responses: Record<string, unknown> = {
      "/api/v1/health": { status: "ok", version: "0.1.0", db: "ok" },
      "/api/v1/imports": [],
      "/api/v1/identification": runs,
      "/api/v1/browse/roots": { input: "", output: "", detected: [] },
    };
    if (!(pathname in responses)) {
      await route.fulfill({ status: 404, json: { code: "SYNTHETIC_ROUTE_NOT_FOUND", message: pathname } });
      return;
    }
    await route.fulfill({ json: responses[pathname] });
  });

  const upload = async () => {
    const nextUpload = uploads + 1;
    await page.locator('input[type="file"]').setInputFiles({
      name: "nomenclature.xlsx",
      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      buffer: Buffer.from("synthetic workbook"),
    });
    await expect(page.locator('input[type="text"]').first()).toHaveValue(pathFor(nextUpload));
  };
  const nomenclature = page.locator(".identification-analysis-grid > section").first();
  return {
    previews, analyses, runs, upload, nomenclature, pathFor,
    delay: (kind: "preview" | "analysis") => { delayed = kind; },
    release: () => { expect(release).toBeDefined(); release?.(); },
  };
}

test("same-named imports stay separate and only load previews on demand", async ({ page }) => {
  const mock = await mockNomenclatures(page);
  await page.goto("/identification");
  await mock.upload();
  await page.waitForTimeout(600); // Exceeds the former automatic-preview debounce.
  expect(mock.previews).toEqual([]);
  expect(mock.analyses).toEqual([]);
  await mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ }).click();
  await expect(mock.nomenclature.getByText("Preview A", { exact: true })).toBeVisible();
  await mock.nomenclature.getByRole("button", { name: /^(Analyser|Analyze)$/ }).click();
  await expect(mock.nomenclature.getByRole("cell", { name: /RESULT-A/ })).toBeVisible();

  await mock.upload();
  await expect(mock.nomenclature.getByRole("cell", { name: /RESULT-A/ })).toHaveCount(0);
  await expect(mock.nomenclature.locator(".preview-table")).toHaveCount(0);
  await page.waitForTimeout(600);
  expect(mock.previews).toEqual([mock.pathFor(1)]);
  expect(mock.analyses).toEqual([mock.pathFor(1)]);
  await mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ }).click();
  await expect(mock.nomenclature.getByText("Preview B", { exact: true })).toBeVisible();
  await expect(page.locator("#nomen-map-sin")).toHaveValue("0");
  await expect(page.locator("#nomen-map-designation")).toHaveValue("1");
  await mock.nomenclature.getByRole("button", { name: /^(Analyser|Analyze)$/ }).click();
  await expect(mock.nomenclature.getByRole("cell", { name: "RESULT-B", exact: true })).toBeVisible();
  expect(mock.analyses).toEqual([mock.pathFor(1), mock.pathFor(2)]);

  const imported = page.locator(".identification-import-list .item-row");
  await expect(imported).toHaveCount(2);
  await imported.last().getByRole("button", { name: /^(Voir|View)$/ }).click();
  await expect(page.locator('input[type="text"]').first()).toHaveValue(mock.pathFor(1));
  await expect(mock.nomenclature.getByRole("cell", { name: /RESULT-A/ })).toBeVisible();
  await expect(mock.nomenclature.getByRole("cell", { name: "RESULT-B", exact: true })).toHaveCount(0);
});

test("highlights duplicate SINs across the full nomenclature", async ({ page }) => {
  const mock = await mockNomenclatures(page);
  await page.goto("/identification");
  await mock.upload();
  await mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ }).click();
  await mock.nomenclature.getByRole("button", { name: /^(Analyser|Analyze)$/ }).click();

  await expect(mock.nomenclature.getByText(/^(Doublon SIN|Duplicate SIN)$/)).toHaveCount(2);
  const filter = mock.nomenclature.getByLabel(/^(Champ de filtre|Filter field)$/);
  await filter.selectOption("monoBody");
  await filter.selectOption("sinDuplicates");
  await expect(mock.nomenclature.locator("table.tbl tbody tr")).toHaveCount(2);
  await expect(mock.nomenclature.getByText(/^(Doublon SIN|Duplicate SIN)$/)).toHaveCount(2);
});

for (const kind of ["preview", "analysis"] as const) {
  test(`a late ${kind} response cannot reactivate the previous file`, async ({ page }) => {
    const mock = await mockNomenclatures(page);
    await page.goto("/identification");
    await mock.upload();
    if (kind === "analysis") {
      await mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ }).click();
      await expect(mock.nomenclature.getByText("Preview A", { exact: true })).toBeVisible();
    }
    mock.delay(kind);
    await mock.nomenclature.getByRole("button", {
      name: kind === "preview" ? /^(Aperçu|Preview)$/ : /^(Analyser|Analyze)$/,
    }).click();
    await expect.poll(() => kind === "preview" ? mock.previews.length : mock.analyses.length).toBe(1);
    await mock.upload();
    mock.release();
    await expect(mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ })).toBeEnabled();
    await expect(page.locator('input[type="text"]').first()).toHaveValue(mock.pathFor(2));
    await expect(mock.nomenclature.locator(".preview-table")).toHaveCount(0);
    await expect(mock.nomenclature.getByRole("cell", { name: "RESULT-A", exact: true })).toHaveCount(0);
    await mock.nomenclature.getByRole("button", { name: /^(Aperçu|Preview)$/ }).click();
    await expect(mock.nomenclature.getByText("Preview B", { exact: true })).toBeVisible();
  });
}
