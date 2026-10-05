import { expect, test } from "@playwright/test";

test("ECM Rename workspace renders", async ({ page }) => {
  await page.route("**/api/v1/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", version: "0.1.0", db: "ok", llm: "disabled" }),
    }),
  );
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        api_key_set: false,
        base_url: "https://api.mistral.ai",
        chat_model: "mistral-small-latest",
        embed_model: "mistral-embed",
        llm_enabled: false,
        llm_tested: false,
      }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("complementary").getByText("ECM-rename", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Analyser les PDF|Analyze PDFs/ })).toBeVisible();

  await page.getByRole("button", { name: "EN" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await page.getByRole("button", { name: "FR" }).click();
  await expect(page.getByRole("heading", { name: "Paramètres" })).toBeVisible();
  await expect(page.getByText("Le traitement ECM n'utilise pas de LLM.")).toBeVisible();
});
