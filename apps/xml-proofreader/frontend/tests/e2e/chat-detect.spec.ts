// E2E for D2 (Chunk 23): a chat detection action returns structured finding
// cards with "Send to Issues" / "Send all"; sending inserts anchored Issues.
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

async function loadSampleAndChatMock(page: Page, responseJson: string) {
  await page.evaluate(({ xml, json }) => {
    const h = (window as unknown as {
      __docreview: { load: (n: string, x: string) => void; __chat: { enable: () => void; mock: (j: string) => void } };
    }).__docreview;
    h.load("bogie_maintenance.dita", xml);
    h.__chat.enable();
    h.__chat.mock(json);
  }, { xml: SAMPLE, json: responseJson });
}

test("Check grammar returns finding cards; Send to Issues populates the Issues tab", async ({ page }) => {
  await signIn(page);
  // "25,000 km" is a literal, visible substring in the sample document.
  await loadSampleAndChatMock(page, JSON.stringify({
    findings: [
      { rule: "grammar", severity: "warning", message: "Chat-detected finding", quote: "25,000 km", replacement: "25 000 km" },
    ],
  }));

  await page.locator(".rp-tab", { hasText: "AI Chat" }).click();
  await page.locator(".chat-action-chip", { hasText: "Check grammar" }).click();

  // Structured finding card appears (not free chat text).
  const finding = page.locator(".chat-finding").filter({ hasText: "Chat-detected finding" });
  await expect(finding).toBeVisible();
  await expect(finding.locator(".cf-repl")).toContainText("25 000 km");

  // Send it to the Issues tab.
  await finding.locator(".cf-send").click();
  await expect(page.locator(".rp-tab.active", { hasText: "Issues" })).toBeVisible();
  await expect(page.locator(".icard").filter({ hasText: "Chat-detected finding" })).toBeVisible();
});
