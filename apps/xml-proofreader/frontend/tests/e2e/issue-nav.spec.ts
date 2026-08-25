// E2E for F5 (Chunk 37): clicking an issue card whose quote is locatable in the
// document scrolls the viewer to that anchor. Uses a Playwright browser where
// scrollIntoView is fully supported (jsdom does not implement it — that's why
// the navigation behavior cannot be tested in the Vitest unit suite; see
// tests/unit/issue-nav.test.ts for the pure findSpanByOffset unit tests).
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

// "25,000 km" is a literal, visible substring near the end of the sample body.
const QUOTE = "25,000 km";

test("clicking an issue card scrolls the document to the quoted anchor (F5)", async ({ page }) => {
  await signIn(page);
  await loadSample(page);

  const mock = JSON.stringify({
    findings: [
      { rule: "Unit rule", severity: "warning", message: "Check unit usage", quote: QUOTE },
    ],
  });
  await enableGraderMock(page, mock);

  // Open the AI Proofreader tab and run the check.
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await page.getByRole("button", { name: /Proofread document/ }).click();

  // Wait until the issue appears in the Issues tab.
  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();
  const issueCard = page.locator(".icard").filter({ hasText: "Check unit usage" });
  await expect(issueCard).toBeVisible();

  // Scroll the document area to the top to ensure the quoted text may not be
  // in the viewport before the click (the sample is long enough for this to matter).
  await page.locator(".scroll-area").evaluate((el) => { el.scrollTop = 0; });

  // Click the issue card — this sets activeIssueId and triggers the scroll effect.
  await issueCard.click();

  // After the scroll effect runs, the element containing the quoted text must
  // be in the browser viewport (Playwright isInViewport uses IntersectionObserver).
  const quotedEl = page.locator(".scroll-area").getByText(QUOTE).first();
  await expect(quotedEl).toBeInViewport({ timeout: 3000 });
});

test("issue card click with unlocalizable quote shows a toast (F5 not-found path)", async ({ page }) => {
  await signIn(page);
  await loadSample(page);

  // Inject a finding whose quote is NOT present in the document.
  const mock = JSON.stringify({
    findings: [
      { rule: "Ghost rule", severity: "info", message: "Ghost issue", quote: "text that does not exist anywhere" },
    ],
  });
  await enableGraderMock(page, mock);

  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await page.getByRole("button", { name: /Proofread document/ }).click();
  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();

  const issueCard = page.locator(".icard").filter({ hasText: "Ghost issue" });
  await expect(issueCard).toBeVisible();
  await issueCard.click();

  // The toast with the "no se pudo localizar" message must appear.
  await expect(page.locator(".toast, [role=alert]").filter({ hasText: /localizar/ })).toBeVisible({ timeout: 3000 });
});
