import { expect, test, type Page } from "@playwright/test";

import type { PreliminaryState, ReviewAction } from "../../src/lib/preliminaryTypes";
import type { RequirementRules } from "../../src/lib/preliminaryRules";

function syntheticState(sourceFormat = "docx"): PreliminaryState {
  return {
    revision: 1, active_dm_id: "proc", source_format: sourceFormat, source_changed: false,
    reviews: {
      proc: {
        fingerprint: "synthetic-only", rules_revision: 0, status: "pending", saved_at: null,
        position: { page: 1, scroll_top: 0, selected_id: null },
        passages: Array.from({ length: 18 }, (_, index) => ({
          id: `p${index}`, node_id: `n${index}`, row: null, start: 0, end: 80,
          source_text: `Synthetic source passage ${index}. Disconnect the connector and inspect the assembly.`,
          text: `Synthetic source passage ${index}. Disconnect the connector and inspect the assembly.`,
          page: Math.floor(index / 6) + 1, kind: "paragraph",
          suggested: index === 0 ? "safety" : index === 2 ? "review" : "body",
          rule: index === 0 ? "keywords" : index === 2 ? "multiple" : "unmatched",
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
  let rules: RequirementRules = {
    revision: 0, groups: [{ category: "conditions", kind: "keyword", fr: ["avant"], en: ["before"] }],
  };
  const writes: Array<ReviewAction & { revision: number }> = [];
  let advances = 0;
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "fr"));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let response: unknown = {};
    if (path.endsWith("/health")) response = { status: "ok", llm: "disabled" };
    else if (path.endsWith("/settings/preliminary-rules")) {
      if (route.request().method() === "POST") {
        const payload = route.request().postDataJSON() as RequirementRules;
        rules = { ...payload, revision: rules.revision + 1 };
      }
      response = rules;
    }
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
    else if (path.endsWith("/wizard/advance")) {
      advances += 1;
      response = {
        step: "generate", dms: [], steps: ["split", "type", "structure", "preliminary", "generate"],
      };
    }
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
      else if (action.op === "skip") {
        for (const skipped of Object.values(state.reviews)) {
          skipped.status = "skipped";
          skipped.saved_at = "2026-10-27T14:00:00Z";
        }
      }
      else if (action.op === "cursor") review.position = {
        page: action.page ?? 1, scroll_top: action.scroll_top ?? 0, selected_id: action.selected_id ?? null,
      };
      response = state;
    } else if (path.endsWith("/pages")) response = Array.from({
      length: Math.max(1, ...state.reviews.proc!.passages.map((passage) => passage.page ?? 1)),
    }, (_, index) => ({ page: index + 1, width: 600, height: 800 }));
    else if (path.includes("/page/")) response = {
      width: 600, height: 800,
      anchors: Object.fromEntries(state.reviews.proc!.passages
        .filter((passage) => passage.page === Number(path.split("/").pop()))
        .map((passage, index) => [passage.id, [[0.1, 0.1 + index * 0.1, 0.8, 0.15 + index * 0.1]]])),
    };
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
  return {
    writes, read: () => state, advances: () => advances,
    fail: (value: boolean) => { failSave = value; },
  };
}

test("classifies, scrolls continuously, and restores after reopening without advancing", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Revoir le DM de procédure" })).toBeVisible();
  const first = page.locator("article").first();
  await first.getByLabel("Décision de classement").selectOption("safety");
  await expect(first.getByLabel("Décision de classement")).toHaveValue("safety");
  const reader = page.getByTestId("procedure-reader");
  await expect(reader.locator("[data-passage]").first()).toHaveText(/Synthetic source passage 0/);
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

test("saving rules in Settings flags an already-open review without discarding its decisions", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await page.locator("article").first().getByLabel("Décision de classement").selectOption("safety");
  await expect(page.locator("article").first().getByLabel("Décision de classement")).toHaveValue("safety");
  await page.getByRole("link", { name: "Paramètres", exact: true }).click();
  await page.getByRole("button", { name: "Afficher les règles", exact: true }).click();
  const form = page.getByRole("form", { name: "Règles de préremplissage des exigences" });
  const category = form.getByTestId("rule-category-conditions");
  await category.locator("summary").first().click();
  await category.locator("fieldset").first().getByLabel("Liste française (FR)").fill("avant\navant intervention");
  await form.getByRole("button", { name: "Enregistrer les règles", exact: true }).click();
  await expect(form.getByRole("status")).toContainText("révision 1");
  await page.getByRole("link", { name: "Migration", exact: true }).click();
  await expect(page.getByRole("button", { name: "Recommencer cette revue", exact: true })).toBeVisible();
  expect(server.read().reviews.proc!.passages[0]?.decision).toBe("safety");
  expect(server.writes.some((write) => write.op === "restart")).toBe(false);
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
  const reader = page.getByTestId("procedure-reader");
  await expect(reader.locator("[data-page]")).toHaveCount(3);
  await expect(reader.locator("[data-passage]")).toHaveCount(0);
  await expect(reader.getByText(/Synthetic source passage/)).toHaveCount(0);
  await expect(page.getByRole("img", { name: "Page PDF source 1" })).toBeVisible();
  const passageList = page.getByTestId("passage-list");
  const [readerBox, listBox] = await Promise.all([
    reader.boundingBox(), passageList.boundingBox(),
  ]);
  if (!readerBox || !listBox) throw new Error("Review scroll boxes are not visible.");
  expect(Math.abs(
    readerBox.y + readerBox.height - listBox.y - listBox.height,
  )).toBeLessThan(2);
  await page.locator("article").first().getByRole("button", { name: /Voir la source/ }).click();
  await expect(page.locator("[data-source-anchor]").first()).toBeVisible();
  await page.locator("article").nth(12).getByRole("button", { name: /Voir la source/ }).click();
  const anchor = reader.locator('[data-source-passage="p12"]').first();
  await expect(anchor).toBeVisible();
  await expect.poll(async () => {
    const [frame, box] = await Promise.all([reader.boundingBox(), anchor.boundingBox()]);
    return Boolean(frame && box && box.y >= frame.y && box.y + box.height <= frame.y + frame.height);
  }).toBe(true);
  await page.screenshot({ path: "test-results/preliminary-dark.png", fullPage: true });
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await page.setViewportSize({ width: 768, height: 900 });
  await expect(page.getByTestId("procedure-reader")).toBeVisible();
  const [tabletReaderBox, tabletListBox] = await Promise.all([
    reader.boundingBox(), passageList.boundingBox(),
  ]);
  if (!tabletReaderBox || !tabletListBox) throw new Error("Tablet review scroll boxes are not visible.");
  expect(Math.abs(tabletReaderBox.height - tabletListBox.height)).toBeLessThan(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/preliminary-light-tablet.png", fullPage: true });
});

test("clear proposals await confirmation while ambiguity requires a decision", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  const cards = page.locator("article");
  await expect(cards.nth(0).locator("select option:checked")).toHaveText("Sécurité");
  await expect(cards.nth(1).locator("select option:checked")).toHaveText("Reste dans la procédure");
  await expect(cards.nth(2).locator("select option:checked")).toHaveText("À trancher");
  expect(server.writes.filter((action) => action.op === "decide")).toHaveLength(0);
  expect(server.read().reviews.proc!.passages.every((passage) => passage.decision === null)).toBe(true);
  const complete = page.getByRole("button", { name: "Marquer cette procédure comme vérifiée" });
  await expect(complete).toBeDisabled();
  const collapseButton = cards.nth(0).getByRole("button", { name: "Replier le passage" });
  await expect(collapseButton).toHaveText("Page source 1");
  await expect(collapseButton.locator("svg")).toBeVisible();
  const filter = page.getByLabel("Afficher les passages");
  await filter.selectOption("safety");
  await expect(cards).toHaveCount(1);
  await filter.selectOption("all");
  await expect(cards).toHaveCount(18);
  await cards.nth(0).getByRole("button", { name: "Accepter la proposition" }).click();
  await expect(cards.nth(0).getByLabel("Décision de classement")).toHaveValue("safety");
  const expandButton = cards.nth(0).getByRole("button", { name: "Développer le passage" });
  await expect(expandButton).toHaveText("Page source 1");
  await expect(expandButton.locator("svg")).toBeVisible();
  await expect(expandButton)
    .toHaveAttribute("aria-expanded", "false");
  await expect(cards.nth(0).getByLabel("Décision de classement")).toBeHidden();
  await expect(cards.nth(0).getByText("Proposition : Sécurité")).toBeHidden();
  await expect(complete).toBeDisabled();
  await expandButton.click({ position: { x: 30, y: 16 } });
  await expect(cards.nth(0).getByLabel("Décision de classement")).toBeVisible();
  await expect.poll(() => server.read().reviews.proc!.position.selected_id).toBe("p0");
  const sourcePassage = cards.nth(0).getByRole("button", { name: "Voir la source — page 1" });
  await expect(sourcePassage).toBeVisible();
  await expect(cards.nth(0).getByText("Voir la source — page 1", { exact: true })).toHaveCount(0);
  await sourcePassage.click();
  await expect(cards.nth(0).getByRole("button", { name: "Développer le passage" }))
    .toHaveAttribute("aria-expanded", "false");
  await expect.poll(() => server.read().reviews.proc!.position.selected_id).toBe("p0");
  expect(server.read().reviews.proc!.passages[1]!.decision).toBeNull();
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(cards.nth(1).locator("select option:checked")).toHaveText("Keep in procedure");
  await expect(cards.nth(2).locator("select option:checked")).toHaveText("Decision needed");
});

test("splits source text at a selected word boundary", async ({ page }) => {
  const server = await mockApplication(page);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  const first = page.locator("article").first();
  await first.locator("details > summary").click();
  const slider = first.getByRole("slider", { name: "Position de scission entre les mots" });
  await slider.press("Home");
  await slider.press("ArrowRight");
  await slider.press("ArrowRight");
  await expect(slider).toHaveAttribute("aria-valuetext", "Après le mot 3 sur 11 : « passage »");
  await first.getByRole("button", { name: "Scinder le passage source" }).click();
  expect(server.writes.filter((action) => action.op === "split").slice(-1)[0]?.split_at).toBe(24);
});

test("PDF errors and unlocated passages never reintroduce a text transcription", async ({ page }) => {
  const server = await mockApplication(page, "pdf");
  server.read().reviews.proc!.passages[17]!.page = null;
  await page.route("**/wizard/preliminary/proc/page/2", (route) =>
    route.fulfill({ json: { width: 600, height: 800, anchors: {} } }));
  let failImage = true;
  await page.route(/\/pdf-cut\/preview\/1(?:\?.*)?$/, async (route) => {
    if (failImage) await route.fulfill({ status: 503, body: "Synthetic image failure" });
    else await route.fallback();
  });
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  const reader = page.getByTestId("procedure-reader");
  await page.locator("article").first().getByRole("button", { name: /Voir la source/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Impossible de charger l'image source." })).toBeVisible();
  await expect(reader.locator("[data-source-anchor]")).toHaveCount(0);
  await expect(reader.locator("[data-passage]")).toHaveCount(0);
  await expect(reader.getByText(/Synthetic source passage/)).toHaveCount(0);
  failImage = false;
  await reader.getByRole("button", { name: "Réessayer" }).click();
  await expect(reader.getByRole("img", { name: "Page PDF source 1" })).toBeVisible();
  await expect(reader.locator('[data-source-passage="p0"]')).toHaveCount(1);
  await page.locator("article").nth(6).getByRole("button", { name: /Voir la source/ }).click();
  await expect(page.getByText(/Le passage n'a pas pu être localisé précisément/)).toBeVisible();
  await expect(reader.locator("[data-source-anchor]")).toHaveCount(0);
  await page.locator("article").nth(17).getByRole("button", { name: /Voir la source/ }).click();
  await expect(page.getByText(/La page PDF de ce passage n'est pas déterminée/)).toBeVisible();
  await expect(reader.locator("[data-page]")).toHaveCount(3);
  await expect(reader.getByText(/Synthetic source passage/)).toHaveCount(0);
});

test("PDF-only reading restores the scroll position and selected highlight", async ({ page }) => {
  const server = await mockApplication(page, "pdf");
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await page.locator("article").nth(12).getByRole("button", { name: /Voir la source/ }).click();
  const reader = page.getByTestId("procedure-reader");
  await expect(reader.locator('[data-source-passage="p12"]').first()).toBeVisible();
  await expect.poll(() => server.read().reviews.proc!.position.selected_id).toBe("p12");
  await expect.poll(() => server.read().reviews.proc!.position.scroll_top).toBeGreaterThan(100);
  await expect(page.getByRole("status").filter({ hasText: "Enregistré" })).toBeVisible();
  const position = server.read().reviews.proc!.position.scroll_top;
  const savedPage = server.read().reviews.proc!.position.page;
  await page.reload();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect.poll(() => reader.evaluate((element) => element.scrollTop)).toBeCloseTo(position, 0);
  expect(server.read().reviews.proc!.position.page).toBe(savedPage);
  await expect(reader.locator('[data-source-passage="p12"]').first()).toBeVisible();
  await expect(reader.locator("[data-passage]")).toHaveCount(0);
});

test("source navigation loads an offscreen PDF page before refining the highlight", async ({ page }) => {
  const server = await mockApplication(page, "pdf");
  server.read().reviews.proc!.passages[17]!.page = 12;
  const requestedPages = new Set<number>();
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.includes("/wizard/preliminary/proc/page/")) requestedPages.add(Number(path.split("/").pop()));
  });
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  const reader = page.getByTestId("procedure-reader");
  await expect(reader.getByRole("img", { name: "Page PDF source 1", exact: true })).toBeVisible();
  expect(requestedPages.has(12)).toBe(false);
  await expect(reader.getByRole("img", { name: "Page PDF source 12", exact: true })).toHaveCount(0);
  await page.locator("article").nth(17).getByRole("button", { name: /Voir la source/ }).click();
  const anchor = reader.locator('[data-page="12"] [data-source-passage="p17"]').first();
  await expect(anchor).toBeVisible();
  await expect.poll(async () => {
    const [frame, box] = await Promise.all([reader.boundingBox(), anchor.boundingBox()]);
    return Boolean(frame && box && box.y >= frame.y && box.y + box.height <= frame.y + frame.height);
  }).toBe(true);
  expect(requestedPages.has(12)).toBe(true);
  await expect(reader.getByRole("img", { name: "Page PDF source 12", exact: true })).toBeVisible();
  await expect(reader.locator("[data-passage]")).toHaveCount(0);
});

test("auto-advances after review, distinguishes empty from reviewed and resumes the active procedure", async ({ page }) => {
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
  await expect.poll(() => server.read().active_dm_id).toBe("proc");
  await expect(page.getByLabel("Procédure", { exact: true })).toHaveValue("proc");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review the procedural DM" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByLabel("Procédure", { exact: true })).toHaveValue("proc");
});

test("skips every procedural review and starts generation directly", async ({ page }) => {
  const server = await mockApplication(page, "docx", true);
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();

  await page.getByRole("button", { name: "Ignorer les revues et générer en l'état" }).click();
  const confirm = page.getByRole("button", { name: "Confirmer la génération sans revue" });
  await expect(confirm).toBeVisible();
  await confirm.click();

  await expect.poll(() => Object.values(server.read().reviews)
    .every((review) => review.status === "skipped")).toBe(true);
  await expect.poll(() => server.advances()).toBe(1);
});

test("editorial structure is not classified and closing conditions have their own destination", async ({ page }) => {
  const server = await mockApplication(page);
  const passages = server.read().reviews.proc!.passages;
  for (const passage of passages) passage.decision = "body";
  passages[0] = { ...passages[0]!, suggested: "support", decision: null, phase: "preliminary", rule: "heading" };
  passages[1] = { ...passages[1]!, suggested: "closing", decision: null, phase: "closing", rule: "closing" };
  passages[2] = { ...passages[2]!, suggested: "body", decision: null, phase: "main", rule: "main" };
  passages.unshift(
    { ...passages[0]!, id: "heading", node_id: "heading", kind: "section", role: "heading",
      source_text: "3.2 Tools required", text: "3.2 Tools required", decision: null },
    { ...passages[0]!, id: "header", node_id: "table", row: 0, kind: "table", role: "table-header",
      source_text: "Tool | Qty", text: "Tool | Qty", decision: null },
  );
  await page.goto("/migration");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  const cards = page.locator("article");
  const reader = page.getByTestId("procedure-reader");
  await expect(cards).toHaveCount(18);
  await expect(cards.filter({ hasText: "3.2 Tools required" })).toHaveCount(0);
  await expect(reader.locator('[data-passage="heading"]')).toHaveText("3.2 Tools required");
  await expect(reader.locator('[data-passage="header"]').getByRole("cell")).toHaveText(["Tool", "Qty"]);
  await expect(page.getByText("3 passage(s) sans décision sur 18", { exact: true })).toBeVisible();
  await expect(cards.nth(1).locator("select option:checked")).toHaveText("Conditions de clôture");
  await expect(cards.nth(2).getByText(/Contenu de la procédure/)).toBeVisible();
  for (const index of [0, 1, 2]) {
    await cards.nth(index).getByRole("button", { name: "Accepter la proposition" }).click();
    await expect(cards.nth(index).getByRole("button", { name: "Accepter la proposition" })).toHaveCount(0);
  }
  await expect(page.getByText("0 passage(s) sans décision sur 18", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: /J'ai vérifié le DM entier/ }).check();
  await page.getByRole("button", { name: "Marquer cette procédure comme vérifiée" }).click();
  await expect(page.getByRole("button", { name: "Générer et valider le XML" })).toBeEnabled();
  expect(server.read().reviews.proc!.passages.find((passage) => passage.id === "p1")!.decision).toBe("closing");
  expect(server.read().reviews.proc!.passages.filter((passage) => passage.role).every((passage) => passage.decision === null)).toBe(true);
});
