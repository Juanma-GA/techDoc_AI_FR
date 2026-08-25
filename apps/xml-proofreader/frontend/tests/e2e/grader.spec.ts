// E2E tests for the AI Proofreader tab (renamed from AI Grader).
// The LlmPort (Tauri bridge) is not available in the browser test environment,
// so we verify:
//   1. The AI Proofreader tab is visible and navigable.
//   2. The Proofread button is disabled (browser degradado).
//   3. Default rules from settings are shown as cards.
//   4. Rules can be added and deleted via the card UI.
//   5. Full proofreading flow with mocked LlmPort via window.__docreview.__grader seam.
//   6. Graceful degradation when the LLM returns unparseable JSON.
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

test("AI Proofreader tab is visible", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await expect(page.locator(".rp-tab", { hasText: "AI Proofreader" })).toBeVisible();
});

test("clicking AI Proofreader tab shows the proofreader panel", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await expect(page.locator(".pr-title")).toContainText("AI Proofreader");
  await expect(page.locator(".pr-new-input")).toBeVisible();
});

test("Proofread button is disabled in browser (no Tauri)", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  const runBtn = page.getByRole("button", { name: /Proofread document/ });
  await expect(runBtn).toBeVisible();
  await expect(runBtn).toBeDisabled();
});

test("proofreader unavailability notice shown in browser", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await expect(page.locator(".pr-unavail")).toBeVisible();
});

test("default rules from settings appear as numbered cards", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  // defaultSettings() ships with 2 rules
  await expect(page.locator(".pr-card")).toHaveCount(2);
  await expect(page.locator(".pr-card").first()).toContainText("torque");
});

test("adding a rule creates a card", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  const initialCount = await page.locator(".pr-card").count();
  await page.locator(".pr-new-input").fill("New test rule");
  await page.locator(".pr-new-input").press("Enter");
  await expect(page.locator(".pr-card")).toHaveCount(initialCount + 1);
  await expect(page.locator(".pr-card").last()).toContainText("New test rule");
});

test("deleting a rule removes its card", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  const initialCount = await page.locator(".pr-card").count();
  await page.locator(".pr-card").first().locator(".pr-btn-delete").click();
  await expect(page.locator(".pr-card")).toHaveCount(initialCount - 1);
});

// ── seam tests: full proofreading flow with mocked LlmPort ───────────────────

type DocReviewHarness = {
  load: (n: string, x: string) => void;
  __grader: {
    enable: () => void;
    mock: (responseJson: string) => void;
    reset: () => void;
  };
};

async function enableGraderMock(page: Page, responseJson: string) {
  await page.evaluate((json) => {
    const h = (window as unknown as { __docreview: DocReviewHarness }).__docreview;
    h.__grader.enable();
    h.__grader.mock(json);
  }, responseJson);
}

async function resetGraderMock(page: Page) {
  await page.evaluate(() => {
    (window as unknown as { __docreview: DocReviewHarness }).__docreview.__grader.reset();
  });
}

test("proofreading flow with mocked LlmPort produces a finding in Issues tab", async ({ page }) => {
  await signIn(page);
  await loadSample(page);

  // "25,000 km" is a literal substring in the raw XML buffer of bogie_maintenance.dita.
  const mockResponse = JSON.stringify({
    findings: [{
      rule: "Demo rule",
      severity: "warning",
      message: "Mocked proofreader finding",
      quote: "25,000 km",
    }],
  });
  await enableGraderMock(page, mockResponse);

  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();

  const runBtn = page.getByRole("button", { name: /Proofread document/ });
  await expect(runBtn).not.toBeDisabled();
  await runBtn.click();

  // runGrader redirects to the Issues tab on success.
  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();
  const card = page.locator(".icard").filter({ hasText: "Mocked proofreader finding" });
  await expect(card).toBeVisible();
  await expect(card.locator(".src")).toContainText("proofreader");

  await resetGraderMock(page);
});

test("proofreading with unparseable LLM response shows info issue", async ({ page }) => {
  await signIn(page);
  await loadSample(page);
  await enableGraderMock(page, "not json");

  await page.locator(".rp-tab", { hasText: "AI Proofreader" }).click();
  await page.getByRole("button", { name: /Proofread document/ }).click();

  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();
  const card = page.locator(".icard").filter({ hasText: /unparseable/ });
  await expect(card).toBeVisible();
  await expect(card.locator(".src")).toContainText("proofreader");

  await resetGraderMock(page);
});
