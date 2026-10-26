import { expect, test, type Page } from "@playwright/test";

async function mockEditorServices(page: Page) {
  await page.route("**/api/v1/settings", (route) =>
    route.fulfill({ json: { demo_enabled: false } }),
  );
  await page.route("**/api/v1/health", (route) =>
    route.fulfill({ json: { status: "ok", version: "test", db: "ok", llm: "disabled" } }),
  );
  await page.route("**/api/v1/formats", (route) =>
    route.fulfill({
      json: [{ format: "svg", extension: ".svg", media_type: "image/svg+xml" }],
    }),
  );
  await page.route("**/api/v1/render/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><rect width="120" height="60"/></svg>',
    }),
  );
  await page.route("**/api/v1/assistant/attach", (route) =>
    route.fulfill({
      json: {
        kind: "graph",
        name: "procedure.dsl",
        graph: {
          title: "Synthetic flow",
          direction: "TB",
          lanes: [],
          nodes: [
            { id: "start", label: "Start", type: "start" },
            { id: "end", label: "End", type: "end" },
          ],
          edges: [{ source: "start", target: "end" }],
        },
        text: "",
        truncated: false,
        warnings: [],
      },
    }),
  );
}

test("root redirects to the editor", async ({ page }) => {
  await mockEditorServices(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/editor$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("attached dsl file needs validation before export", async ({ page }) => {
  await mockEditorServices(page);
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
  await mockEditorServices(page);
  await page.goto("/editor");
  const sidebar = page.getByTestId("sidebar");
  await page.getByTestId("sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await expect(sidebar.locator(".ui-nav-icon svg").first()).toBeVisible();
  await expect(sidebar.locator(".ui-nav-label").first()).toBeHidden();
  await expect(sidebar.locator(".ui-llm-badge")).toBeHidden();
  await page.getByTestId("sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  await expect(sidebar.locator(".ui-llm-badge")).toBeVisible();
});
test("assistant generates a flowchart", async ({ page }) => {
  await mockEditorServices(page);
  await page.route("**/api/v1/assistant/chat", (route) =>
    route.fulfill({
      json: {
        message: "Synthetic flow generated.",
        graph: {
          title: "Synthetic flow",
          direction: "TB",
          lanes: [],
          nodes: [
            { id: "start", label: "Start", type: "start" },
            { id: "end", label: "End", type: "end" },
          ],
          edges: [{ source: "start", target: "end" }],
        },
        changed: true,
        llm_used: false,
        warnings: [],
      },
    }),
  );
  await page.goto("/editor");
  await page.getByRole("textbox").fill("Le moteur ne demarre pas.\nVerifier la batterie.\nRemplacer la batterie.");
  await page.getByRole("button", { name: /Envoyer|Send/ }).click();
  await expect(page.getByRole("img")).toBeVisible();
});
