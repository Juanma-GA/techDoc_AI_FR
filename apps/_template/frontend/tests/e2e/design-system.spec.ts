import { expect, test } from "@playwright/test";

// Visual smoke of the shared design system on the dev-only /design gallery:
// both themes, both languages, desktop and narrow viewports. Screenshots are
// attached to the report (no committed baseline: rendering differs per OS).

const THEMES = ["dark", "light"] as const;
const LANGUAGES = ["fr", "en"] as const;
const VIEWPORTS = [
  { name: "desktop", width: 1366, height: 900 },
  { name: "narrow", width: 760, height: 900 },
] as const;

for (const theme of THEMES) {
  for (const language of LANGUAGES) {
    for (const viewport of VIEWPORTS) {
      test(`design gallery ${theme} ${language} ${viewport.name}`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.addInitScript(
          ([savedTheme, savedLanguage]) => {
            localStorage.setItem("theme", savedTheme);
            localStorage.setItem("i18nextLng", savedLanguage);
          },
          [theme, language] as const,
        );
        await page.route("**/api/v1/settings", (route) =>
          route.fulfill({ json: { demo_enabled: false } }),
        );
        await page.goto("/design");
        await expect(page.getByTestId("design-gallery")).toBeVisible();
        const modelPicker = page.locator("#design-model");
        await modelPicker.click();
        const modelListbox = page.locator("#design-model-listbox");
        await expect(modelListbox).toBeVisible();
        await modelListbox.getByRole("option", { name: "mistral-small-latest" }).click();
        await expect(modelPicker).toContainText("mistral-small-latest");

        const isDark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
        expect(isDark).toBe(theme === "dark");

        // Self-hosted faces are really loaded (no CDN, no silent system fallback).
        const loadedFamilies = await page.evaluate(async () => {
          await document.fonts.ready;
          const families = new Set<string>();
          document.fonts.forEach((face) => {
            if (face.status === "loaded") families.add(face.family.replace(/["']/g, ""));
          });
          return [...families].sort();
        });
        expect(loadedFamilies).toEqual(expect.arrayContaining(["Inter", "JetBrains Mono", "Orbitron"]));

        const overflow = await page.evaluate(() => {
          const main = document.querySelector("main");
          return main ? main.scrollWidth - main.clientWidth : 0;
        });
        expect(overflow).toBeLessThanOrEqual(1);

        await testInfo.attach(`${theme}-${language}-${viewport.name}.png`, {
          body: await page.screenshot({ fullPage: true }),
          contentType: "image/png",
        });
      });
    }
  }
}
