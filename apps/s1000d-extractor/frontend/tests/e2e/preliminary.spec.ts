import { expect, test, type Page } from "@playwright/test";

import type { PreliminaryState, ReviewAction } from "../../src/lib/preliminaryTypes";

function syntheticState(sourceFormat = "docx"): PreliminaryState {
  return {
    revision: 1, active_dm_id: "proc", source_format: sourceFormat, source_changed: false,
    reviews: {
      proc: {
        fingerprint: "synthetic-only", status: "pending", saved_at: null,
        position: { page: 1, scroll_top: 0, selected_id: null },
        passages: Array.from({ length: 18 }, (_, index) => ({
          id: `p${index}`, node_id: `n${index}`, row: null, start: 0, end: 80,
          source_text: `Synthetic source passage ${index}. Disconnect the connector and inspect the assembly.`,
          text: `Synthetic source passage ${index}. Disconnect the connector and inspect the assembly.`,
          page: Math.floor(index / 6) + 1, kind: "paragraph",
          suggested: index === 0 ? "safety" : "body", rule: index === 0 ? "keywords" : "unmatched",
          decision: null,
        })),
      },
    },
  };
}

async function mockApplication(page: Page, sourceFormat = "docx", includeEmpty = false) {
  let state = syntheticState(sourceFormat);
  if (includeEmpty) state.reviews.empty = {
    fingerprint: "synthetic-empty", status: "pending", passages: [],
    position: { page: 1, scroll_top: 0, selected_id: null }, saved_at: null,
  };
  let failSave = false;
  const writes: Array<ReviewAction & { revision: number }> = [];
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let response: unknown = {};
    if (path.endsWith("/health")) response = { status: "ok", llm: "disabled" };
    else if (path.endsWith("/settings")) response = { demo_enabled: false, llm_enabled: false };
    else if (path.endsWith("/documents")) response = [{
      id: "synthetic-doc", filename: "synthetic-source.docx", source_format: sourceFormat, status: "wizard",
    }];
    else if (path.endsWith("/wizard")) response = {
      step: "preliminary", split_level: "section", preliminary: state,
      steps: ["split", "type", "structure", "preliminary", "generate"],
      dms: Object.keys(state.reviews).map((id) => ({
        dm_id: id, dm_type: "procedural",
        title: id === "proc" ? "Synthetic removal" : "Synthetic empty", node_count: 18,
      })),
    };
    else if (path.endsWith("/wizard/preliminary")) {
      if (failSave) {
        await route.fulfill({ status: 503, json: { code: "SYNTHETIC_FAILURE", message: "Synthetic save failure" } });
        return;
      }
      const action = route.request().postDataJSON() as ReviewAction & { revision: number };
      writes.push(action);
      if (action.revision !== state.revision) {
        await route.fulfill({ status: 409, json: { code: "REVIEW_CONFLICT", message: "Synthetic conflict" } });
        return;
      }
      state = structuredClone(state);
      const review = state.reviews[action.dm_id]!;
      state.active_dm_id = action.dm_id;
      state.revision += 1;
      review.saved_at = "2026-10-27T14:00:00Z";
      if (action.op === "decide") {
        const passage = review.passages.find((p) => p.id === action.passage_id)!;
        if ("destination" in action) passage.decision = action.destination ?? null;
        passage.text = action.text ?? passage.text;
      } else if (action.op === "complete") review.status = "reviewed";
      else if (action.op === "cursor") review.position = {
        page: action.page ?? 1, scroll_top: action.scroll_top ?? 0, selected_id: action.selected_id ?? null,
      };
      response = state;
    } else if (path.endsWith("/pages")) response = [1, 2, 3].map((number) => ({ page: number, width: 600, height: 800 }));
    else if (path.includes("/page/")) response = { width: 600, height: 800, anchors: { p0: [[0.1, 0.1, 0.8, 0.15]] } };
    else if (path.includes("/pdf-cut/preview/")) {
      await route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800"><rect width="600" height="800" fill="white"/><text x="60" y="100">Synthetic PDF page</text></svg>',
      });
      return;
    } else if (path.includes("/brex")) response = [];
    else if (path.includes("/migration-inputs")) response = [];
    await route.fulfill({ json: response });
  });
  return { writes, read: () => state, fail: (value: boolean) => { failSave = value; } };
}

test("classifies, scrolls continuously, and restores after reopening without advancing", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Revoir les exigences préliminaires" })).toBeVisible();
  const first = page.locator("article").first();
  await first.getByLabel("Décision de classement").selectOption("safety");
  await expect(first.getByLabel("Décision de classement")).toHaveValue("safety");
  const reader = page.getByTestId("procedure-reader");
  await reader.hover();
  await page.mouse.wheel(0, 500);
  await expect.poll(() => server.read().reviews.proc!.position.scroll_top).toBeGreaterThan(100);
  const position = server.read().reviews.proc!.position.scroll_top;
  await expect(page.getByRole("status").filter({ hasText: "Enregistré" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect.poll(() => reader.evaluate((element) => element.scrollTop)).toBeCloseTo(position, 0);
  await expect(page.locator("article").first().getByLabel("Décision de classement")).toHaveValue("safety");
  expect(server.writes.some((action) => action.op === "cursor")).toBe(true);
});

test("exposes a failed save and retries without claiming success", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  server.fail(true);
  await page.locator("article").first().getByLabel("Décision de classement").selectOption("safety");
  await expect(page.getByRole("alert").filter({ hasText: "Synthetic save failure" })).toBeVisible();
  await expect(page.locator("article").first().getByLabel("Décision de classement")).toHaveValue("");
  server.fail(false);
  await page.getByRole("button", { name: "Réessayer", exact: true }).click();
  await expect(page.locator("article").first().getByLabel("Décision de classement")).toHaveValue("safety");
});

test("PDF pages load progressively with source highlighting in dark and light layouts", async ({ page }) => {
  await mockApplication(page, "pdf");
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByTestId("procedure-reader").locator("[data-page]")).toHaveCount(3);
  await expect(page.getByRole("img", { name: "Page PDF source 1" })).toBeVisible();
  await page.locator("article").first().getByRole("button", { name: /Voir la source/ }).click();
  await expect(page.locator("[data-source-anchor]").first()).toBeVisible();
  await page.screenshot({ path: "test-results/preliminary-dark.png", fullPage: true });
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.getByTestId("procedure-reader")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/preliminary-light-tablet.png", fullPage: true });
});

test("distinguishes empty from reviewed, changes language and resumes the active procedure", async ({ page }) => {
  const server = await mockApplication(page, "docx", true);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await page.getByLabel("Procédure", { exact: true }).selectOption("empty");
  await expect(page.getByText("Procédure 2 sur 2", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Marquer cette procédure comme vérifiée" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Générer et valider le XML" })).toBeDisabled();
  const confirmation = page.getByRole("checkbox", { name: /J'ai vérifié le DM entier/ });
  await confirmation.focus();
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "Marquer cette procédure comme vérifiée" }).click();
  await expect.poll(() => server.read().reviews.empty!.status).toBe("reviewed");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review preliminary requirements" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByLabel("Procédure", { exact: true })).toHaveValue("empty");
});
