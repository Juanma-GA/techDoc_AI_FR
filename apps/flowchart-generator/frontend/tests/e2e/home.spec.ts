import { expect, test } from "@playwright/test";

test("root redirects to the editor", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/editor$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("attached dsl file needs validation before export", async ({ page }) => {
  await page.goto("/editor");
  const dsl = "title: Demarrage\nS [start] Moteur ne demarre pas\nE [end] Fin\nS -> E\n";
  await page.getByTestId("assistant-file-input").setInputFiles({
    name: "procedure.dsl",
    mimeType: "text/plain",
    buffer: Buffer.from(dsl),
  });
  await expect(page.getByRole("img")).toBeVisible();
  await expect(page.getByTestId("export-bar")).toHaveCount(0);
  await page.getByTestId("validate-flow").click();
  await expect(page.getByTestId("export-bar")).toBeVisible();
});

test("sidebar collapses and expands", async ({ page }) => {
  await page.goto("/editor");
  const sidebar = page.getByTestId("sidebar");
  await page.getByTestId("sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await expect(page.getByTestId("llm-badge")).toBeVisible();
  await page.getByTestId("sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
});
test("assistant generates a flowchart", async ({ page }) => {
  await page.goto("/editor");
  await page.getByRole("textbox").fill("Le moteur ne demarre pas.\nVerifier la batterie.\nRemplacer la batterie.");
  await page.getByRole("button", { name: /Envoyer|Send/ }).click();
  await expect(page.getByRole("img")).toBeVisible();
});
