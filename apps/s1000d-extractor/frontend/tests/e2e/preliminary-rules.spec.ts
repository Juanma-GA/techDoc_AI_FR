import { expect, test, type Locator, type Page } from "@playwright/test";

import type { RequirementRules } from "../../src/lib/preliminaryRules";
import { requirementCategories } from "../../src/lib/preliminaryTypes";

async function mockSettings(page: Page, language = "fr", termCount = 1, categoryCount = 1) {
  let state: RequirementRules = {
    revision: 0,
    groups: requirementCategories.slice(0, categoryCount).map((category) => ({
      category, kind: "keyword",
      fr: Array.from({ length: termCount }, (_, index) =>
        category === "conditions" && !index ? "banc isolé" : `${category} synthétique ${index}`),
      en: Array.from({ length: termCount }, (_, index) =>
        category === "conditions" && !index ? "isolated bench" : `Synthetic ${category} ${index}`),
    })),
  };
  let failure = 0;
  let readFailure = false;
  const writes: RequirementRules[] = [];
  await page.addInitScript((lng) => localStorage.setItem("i18nextLng", lng), language);
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let response: unknown = [];
    if (path.endsWith("/preliminary-rules")) {
      if (route.request().method() === "POST") {
        const payload = route.request().postDataJSON() as RequirementRules;
        if (failure) {
          await route.fulfill({
            status: failure, json: { code: failure === 409 ? "RULES_CONFLICT" : "SYNTHETIC_FAILURE", message: "Synthetic save failure" },
          });
          return;
        }
        writes.push(payload);
        state = { revision: state.revision + 1, groups: payload.groups };
      } else if (readFailure) {
        await route.fulfill({ status: 503, json: { code: "SYNTHETIC_FAILURE", message: "Synthetic read failure" } });
        return;
      }
      response = state;
    } else if (path.endsWith("/settings")) response = {
      api_key_set: false, base_url: "", chat_model: "", embed_model: "", llm_enabled: false, demo_enabled: false,
    };
    else if (path.endsWith("/health")) response = { status: "ok", llm: "disabled" };
    await route.fulfill({ json: response });
  });
  return {
    writes, read: () => state, fail: (status: number) => { failure = status; },
    failRead: (value: boolean) => { readFailure = value; },
  };
}

async function openRules(page: Page, language = "fr") {
  await page.getByRole("button", { name: language === "fr" ? "Afficher les règles" : "Show rules", exact: true }).click();
}

async function openCategory(page: Page, category = "conditions") {
  const section = page.getByTestId(`rule-category-${category}`);
  await section.locator("summary").first().click();
  return section;
}

async function saveRules(form: Locator, destructive = false) {
  await form.getByRole("button", { name: "Enregistrer les règles", exact: true }).click();
  if (destructive) await form.getByRole("button", { name: "Cliquer encore pour confirmer", exact: true }).click();
}

test("edits category lists with independent counts and persists additions, replacements and removals", async ({ page }) => {
  const server = await mockSettings(page);
  await page.goto("/settings");
  await openRules(page);
  const form = page.getByRole("form", { name: "Règles de préremplissage des exigences" });
  await expect(form.locator('[data-testid^="rule-category-"]')).toHaveCount(6);
  await expect(form.locator("input, select, [data-rule-index]")).toHaveCount(0);
  const category = await openCategory(page);
  const lists = category.locator("fieldset").first();
  await lists.getByLabel("Liste française (FR)").fill(" banc isolé \n\nzone dégagée\n");
  await saveRules(form);
  await expect(form.getByRole("status")).toContainText("révision 1");
  expect(server.writes[0]?.groups[0]).toMatchObject({
    fr: ["banc isolé", "zone dégagée"], en: ["isolated bench"],
  });
  await page.reload();
  await openRules(page);
  await openCategory(page);
  await expect(lists.getByLabel("Liste française (FR)")).toHaveValue("banc isolé\nzone dégagée");
  await lists.getByLabel("Liste anglaise (EN)").fill("clear working area");
  await form.getByRole("button", { name: "Enregistrer les règles", exact: true }).click();
  expect(server.writes).toHaveLength(1);
  await form.getByRole("button", { name: "Cliquer encore pour confirmer", exact: true }).click();
  await expect(form.getByRole("status")).toContainText("révision 2");
  await lists.getByLabel("Liste française (FR)").fill("banc isolé");
  await saveRules(form, true);
  await expect(form.getByRole("status")).toContainText("révision 3");
  await page.reload();
  await openRules(page);
  await openCategory(page);
  await expect(lists.getByLabel("Liste anglaise (EN)")).toHaveValue("clear working area");
  expect(server.read().groups).toEqual([{
    category: "conditions", kind: "keyword", fr: ["banc isolé"], en: ["clear working area"],
  }]);
});

test("keeps heading lists separate and requires both languages without pairing lines", async ({ page }) => {
  const server = await mockSettings(page);
  await page.goto("/settings");
  await openRules(page);
  const form = page.getByRole("form");
  const category = await openCategory(page, "support");
  await category.getByText("Titres de section ou colonne", { exact: true }).first().click();
  const headings = category.locator("fieldset").last();
  await headings.getByLabel("Liste française (FR)").fill("Équipements de banc");
  await expect(form.getByRole("button", { name: "Enregistrer les règles", exact: true })).toBeDisabled();
  await expect(form.getByRole("alert")).toContainText("renseignez FR et EN");
  await headings.getByLabel("Liste anglaise (EN)").fill("Bench resources\nBench fixtures");
  await saveRules(form);
  await expect(form.getByRole("status")).toContainText("révision 1");
  expect(server.read().groups[1]).toEqual({
    category: "support", kind: "heading", fr: ["Équipements de banc"], en: ["Bench resources", "Bench fixtures"],
  });
});

test("retains edits on save failure and handles a conflicting settings tab explicitly", async ({ page }) => {
  const server = await mockSettings(page);
  await page.goto("/settings");
  await openRules(page);
  const form = page.getByRole("form");
  const category = await openCategory(page);
  const french = category.locator("fieldset").first().getByLabel("Liste française (FR)");
  await french.fill("banc isolé\nbanc sécurisé");
  server.fail(503);
  await saveRules(form);
  await expect(form.getByRole("alert")).toContainText("Synthetic save failure");
  await expect(french).toHaveValue("banc isolé\nbanc sécurisé");
  expect(server.read().revision).toBe(0);
  server.fail(409);
  await saveRules(form);
  await expect(form.getByRole("alert")).toContainText("autre fenêtre");
  await form.getByRole("button", { name: "Recharger les règles enregistrées", exact: true }).click();
  await expect(french).toHaveValue("banc isolé\nbanc sécurisé");
  await form.getByRole("button", { name: "Cliquer encore pour confirmer", exact: true }).click();
  await expect(french).toHaveValue("banc isolé");
  server.fail(0);
  await french.fill("banc isolé\nbanc sécurisé");
  await saveRules(form);
  await expect(form.getByRole("status")).toContainText("révision 1");
});

test("reports a loading failure and offers a working retry", async ({ page }) => {
  const server = await mockSettings(page);
  server.failRead(true);
  await page.goto("/settings");
  await openRules(page);
  const error = page.getByRole("alert").filter({ hasText: "Impossible de charger les règles" });
  await expect(error).toBeVisible({ timeout: 15000 });
  server.failRead(false);
  await error.getByRole("button", { name: "Réessayer", exact: true }).click();
  await expect(page.getByRole("form", { name: "Règles de préremplissage des exigences" })).toBeVisible();
});

test("supports English, keyboard confirmation and intentional empty configuration", async ({ page }) => {
  const server = await mockSettings(page, "en");
  await page.goto("/settings");
  await openRules(page, "en");
  const form = page.getByRole("form", { name: "Requirement prefill rules" });
  const category = await openCategory(page);
  const lists = category.locator("fieldset").first();
  await expect(lists.getByLabel("French list (FR)")).toHaveValue("banc isolé");
  await lists.getByLabel("French list (FR)").fill("");
  await expect(form.getByRole("button", { name: "Save rules", exact: true })).toBeDisabled();
  await lists.getByLabel("English list (EN)").fill("");
  await form.getByRole("button", { name: "Save rules", exact: true }).focus();
  await page.keyboard.press("Space");
  expect(server.writes).toHaveLength(0);
  await page.keyboard.press("Enter");
  await expect(form.getByRole("status")).toContainText("revision 1");
  expect(server.read().groups).toEqual([]);
  await page.reload();
  await openRules(page, "en");
  await openCategory(page);
  await expect(lists.getByLabel("French list (FR)")).toHaveValue("");
});

test("clicks the entire header without folding when editing lists or opening categories", async ({ page }) => {
  const server = await mockSettings(page);
  await page.goto("/settings");
  const panel = page.getByTestId("preliminary-rules-panel");
  const header = page.getByTestId("preliminary-rules-header");
  await header.click({ position: { x: 4, y: 4 } });
  const toggle = header.getByRole("button");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  const category = await openCategory(page);
  const expression = category.locator("fieldset").first().getByLabel("Liste française (FR)");
  await expression.fill("banc sécurisé");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await category.locator("summary").first().click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await category.locator("summary").first().click();
  await header.click({ position: { x: 24, y: 30 } });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await header.click({ position: { x: 4, y: 4 } });
  await expect(expression).toHaveValue("banc sécurisé");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(panel.getByText("Modifications non enregistrées", { exact: true })).toBeVisible();
  expect(server.writes).toHaveLength(0);
});

test("folds with the keyboard while retaining category state and unsaved list edits", async ({ page }) => {
  await mockSettings(page);
  await page.goto("/settings");
  const panel = page.getByTestId("preliminary-rules-panel");
  const expand = panel.getByRole("button", { name: "Afficher les règles", exact: true });
  await expand.focus();
  await page.keyboard.press("Enter");
  const category = await openCategory(page);
  const expression = category.locator("fieldset").first().getByLabel("Liste française (FR)");
  await expression.fill("banc isolé\nbanc sécurisé");
  await panel.getByRole("button", { name: "Replier les règles", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(panel.getByRole("form")).toBeHidden();
  await openRules(page);
  await expect(category).toHaveAttribute("open", "");
  await expect(expression).toHaveValue("banc isolé\nbanc sécurisé");
});

for (const layout of [
  { width: 1440, height: 1000, language: "fr", dark: true },
  { width: 1024, height: 900, language: "fr", dark: true },
  { width: 768, height: 1000, language: "fr", dark: false },
  { width: 1280, height: 900, language: "en", dark: false },
  { width: 390, height: 844, language: "en", dark: true },
]) {
  test(`keeps six compact categories and unclipped lists at ${layout.width}px (${layout.language}, ${layout.dark ? "dark" : "light"})`, async ({ page }) => {
    await page.setViewportSize({ width: layout.width, height: layout.height });
    await mockSettings(page, layout.language, 50, 6);
    await page.goto("/settings");
    await page.evaluate((dark) => document.documentElement.classList.toggle("dark", dark), layout.dark);
    const gaps = await page.getByTestId("settings-sections").evaluate((element) => {
      const boxes = [...element.children].map((child) => child.getBoundingClientRect());
      return boxes.slice(1).map((box, index) => box.top - boxes[index]!.bottom);
    });
    expect(gaps).toHaveLength(3);
    for (const gap of gaps) expect(gap).toBeGreaterThanOrEqual(16);
    await openRules(page, layout.language);
    const panel = page.getByTestId("preliminary-rules-panel");
    const form = panel.getByRole("form");
    await expect(form.locator('[data-testid^="rule-category-"]')).toHaveCount(6);
    await expect(form.locator("textarea")).toHaveCount(24);
    await expect(form.locator("input, select, [data-rule-index]")).toHaveCount(0);
    const name = `rules-${layout.width}-${layout.language}-${layout.dark ? "dark" : "light"}`;
    await panel.evaluate((element) => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: `test-results/${name}-categories.png` });
    for (const category of requirementCategories) await openCategory(page, category);
    const metrics = await form.locator("textarea").evaluateAll((controls) => controls.flatMap((control) => {
      // Closed native details can still report descendant layout rectangles.
      if (control.closest("details:not([open])") || !control.getClientRects().length) return [];
      const style = getComputedStyle(control);
      const box = control.getBoundingClientRect();
      const label = control.closest("label")?.querySelector("span")?.getBoundingClientRect();
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas measurement unavailable");
      context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      return [{
        contentHeight: box.height - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
          - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth),
        lineHeight: style.lineHeight === "normal" ? parseFloat(style.fontSize) * 1.2 : parseFloat(style.lineHeight),
        textWidth: Math.max(...control.value.split("\n").map((line) => context.measureText(line).width)),
        contentWidth: control.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
        overlapsLabel: label ? label.bottom > box.top + 0.5 : false,
        spillsOutsideLabel: box.width > (control.closest("label")?.clientWidth ?? box.width) + 0.5,
        horizontallyScrollable: control.scrollWidth > control.clientWidth,
      }];
    }));
    expect(metrics).toHaveLength(12);
    for (const metric of metrics) {
      expect(metric.contentHeight, JSON.stringify(metric)).toBeGreaterThanOrEqual(metric.lineHeight * 5 - 1);
      expect(metric.textWidth, JSON.stringify(metric)).toBeLessThanOrEqual(metric.contentWidth + 0.5);
      expect(metric.overlapsLabel, JSON.stringify(metric)).toBe(false);
      expect(metric.spillsOutsideLabel, JSON.stringify(metric)).toBe(false);
      expect(metric.horizontallyScrollable, JSON.stringify(metric)).toBe(false);
    }
    expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    for (const category of requirementCategories.slice(1)) await openCategory(page, category);
    await panel.evaluate((element) => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: `test-results/${name}-expanded.png` });
  });
}
