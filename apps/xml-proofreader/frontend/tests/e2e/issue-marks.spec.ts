// E2E for D5 (Chunk 21): anchored issues are marked in the document via the CSS
// Custom Highlight API (an ephemeral overlay — no buffer/DOM mutation). The marks
// are not DOM nodes, so we assert against the CSS.highlights registry.
import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SAMPLE = readFileSync(join(here, "..", "..", "samples", "bogie_maintenance.dita"), "utf8");

async function signIn(page: Page) {
  await page.goto("/");
  await expect(page.locator(".login-card")).toBeVisible();
  await page.locator(".field input").first().fill("Maria Ruiz");
  await page.locator(".field input").nth(1).fill("maria@atexis.com");
  await page.locator(".field input[type=password]").fill("pw123456");
  await page.getByRole("button", { name: /Create account/ }).click();
  await expect(page.locator(".brand")).toContainText("XML Proofreader");
}

async function loadSample(page: Page) {
  await page.evaluate((xml) => {
    (window as unknown as { __docreview: { load: (n: string, x: string) => void } })
      .__docreview.load("bogie_maintenance.dita", xml);
  }, SAMPLE);
}

async function enableGraderMock(page: Page, responseJson: string) {
  await page.evaluate((json) => {
    const h = (window as unknown as {
      __docreview: { __grader: { enable: () => void; mock: (j: string) => void } };
    }).__docreview;
    h.__grader.enable();
    h.__grader.mock(json);
  }, responseJson);
}

function highlightSizes(page: Page) {
  return page.evaluate(() => {
    const reg = (CSS as unknown as { highlights?: Map<string, { size: number }> }).highlights;
    return {
      all: reg?.get("issue-mark")?.size ?? 0,
      active: reg?.get("issue-mark-active")?.size ?? 0,
    };
  });
}

test("proofread marks the anchored finding in the document and emphasises the active one", async ({ page }) => {
  await signIn(page);
  await loadSample(page);

  // "25,000 km" is a literal, visible substring in the sample document body.
  const mock = JSON.stringify({
    findings: [
      { rule: "Demo rule", severity: "warning", message: "Mocked overlay finding", quote: "25,000 km" },
    ],
  });
  await enableGraderMock(page, mock);

  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await page.getByRole("button", { name: /Proofread document/ }).click();

  // Issue is listed…
  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();
  await expect(page.locator(".icard").filter({ hasText: "Mocked overlay finding" })).toBeVisible();

  // …and marked in the document (no issue active yet → painted by issue-mark).
  await expect.poll(async () => (await highlightSizes(page)).all).toBeGreaterThan(0);

  // Clicking the issue makes it active → it moves to the active highlight.
  await page.locator(".icard").filter({ hasText: "Mocked overlay finding" }).click();
  await expect.poll(async () => (await highlightSizes(page)).active).toBeGreaterThan(0);
});
