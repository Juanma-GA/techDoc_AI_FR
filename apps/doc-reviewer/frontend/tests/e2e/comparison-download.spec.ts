import { expect, test, type Locator } from "@playwright/test";

import type { ComparisonDetail } from "../../src/lib/comparisonApi";

function luminance(color: string): number {
  const channels = color.match(/[\d.]+/g)?.map(Number);
  const [red, green, blue, alpha] = channels ?? [];
  if (
    !color.startsWith("rgb") ||
    red === undefined ||
    green === undefined ||
    blue === undefined ||
    (alpha !== undefined && alpha !== 1)
  ) {
    throw new Error(`Expected an opaque RGB color, received ${color}`);
  }
  const linear = (value: number) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

async function expectReadable(link: Locator): Promise<void> {
  const colors = await link.evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((animation) => animation.finished));
    const style = getComputedStyle(element);
    return { foreground: style.color, background: style.backgroundColor, fontSize: style.fontSize };
  });
  const foreground = luminance(colors.foreground);
  const background = luminance(colors.background);
  const contrast = (Math.max(foreground, background) + 0.05) /
    (Math.min(foreground, background) + 0.05);
  expect(contrast, JSON.stringify(colors)).toBeGreaterThanOrEqual(4.5);
  expect(Number.parseFloat(colors.fontSize)).toBeGreaterThanOrEqual(13);
}

for (const fileCount of [2, 3]) {
  test(`keeps download links readable and preserves export URLs for ${fileCount} PDFs`, async ({ page }, testInfo) => {
    const comparison: ComparisonDetail = {
      id: "synthetic-comparison",
      title: "Synthetic reference",
      created_at: "2026-10-30T12:00:00Z",
      file_count: fileCount,
      ai_status: "disabled",
      ai_summary: null,
      ai_summary_truncated: false,
      report: {
        schema_version: 5,
        reference_index: 0,
        documents: Array.from({ length: fileCount }, (_, index) => ({
          index,
          filename: `synthetic-${index}.pdf`,
          page_count: 1,
        })),
        comparisons: Array.from({ length: fileCount - 1 }, (_, index) => ({
          document_index: index + 1,
          filename: `synthetic-${index + 1}.pdf`,
          added_count: 0,
          removed_count: 0,
          changes: [],
          page_alignment: [],
        })),
        page_slots: [],
      },
    };
    await page.context().route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/settings/mistral") {
        await route.fulfill({ json: { demo_enabled: false, llm_enabled: false } });
      } else if (path === "/api/v1/health") {
        await route.fulfill({
          json: { status: "ok", version: "test", db: "ok", llm: "disabled" },
        });
      } else if (path === "/api/v1/comparisons") {
        await route.fulfill({ json: [comparison] });
      } else if (path === `/api/v1/comparisons/${comparison.id}`) {
        await route.fulfill({ json: comparison });
      } else {
        await route.fulfill({ json: [] });
      }
    });
    await page.goto("/comparison");

    const downloads = page.locator("a[data-comparison-download]");
    await expect(downloads).toHaveCount(fileCount === 2 ? 1 : 2);
    for (const state of [
      { language: "FR", dark: true },
      { language: "FR", dark: false },
      { language: "EN", dark: false },
      { language: "EN", dark: true },
    ]) {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.getByRole("button", { name: state.language, exact: true }).click();
      const isFrench = state.language === "FR";
      await expect(downloads.first()).toContainText(
        fileCount > 2
          ? (isFrench ? "Télécharger la référence avec toutes les différences" : "Download reference with all differences")
          : (isFrench ? "Télécharger le PDF de référence commenté" : "Download commented reference PDF"),
      );
      if (fileCount > 2) {
        await expect(downloads.nth(1)).toContainText(
          isFrench ? "Télécharger la référence pour cette version" : "Download reference for this version",
        );
      }
      const isDark = await page.locator("html").evaluate((root) => root.classList.contains("dark"));
      if (isDark !== state.dark) {
        await page.getByRole("button", { name: isFrench ? "Changer de thème" : "Switch theme" }).click();
      }
      if (state.dark) await expect(page.locator("html")).toHaveClass(/dark/);
      else await expect(page.locator("html")).not.toHaveClass(/dark/);

      for (const link of await downloads.all()) {
        await expect(link).toHaveAttribute("download", "");
        await expect(link).toHaveAttribute("href", new RegExp(`language=${isFrench ? "fr" : "en"}$`));
        await page.mouse.move(0, 0);
        await expectReadable(link);
        await link.hover();
        await expectReadable(link);
        await page.mouse.move(0, 0);
        await page.keyboard.press("Tab");
        await link.focus();
        await expect(link).toBeFocused();
        await expectReadable(link);
        expect(await link.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe("none");
      }
      await downloads.first().scrollIntoViewIfNeeded();
      await page.screenshot({
        path: testInfo.outputPath(`download-${state.language}-${state.dark ? "dark" : "light"}.png`),
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await expect(downloads.first()).toBeVisible();
      expect(await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
      )).toBeLessThanOrEqual(1);
    }

    await expect(downloads.first()).toHaveAttribute(
      "href", `/api/v1/comparisons/${comparison.id}/export?language=en`,
    );
    if (fileCount > 2) {
      await expect(downloads.nth(1)).toHaveAttribute(
        "href", `/api/v1/comparisons/${comparison.id}/export/1?language=en`,
      );
    }
  });
}
