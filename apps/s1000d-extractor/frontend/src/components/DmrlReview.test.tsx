import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { DmrlRow } from "../lib/api";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${Object.values(options).join(",")}` : key,
  }),
}));

import { DmrlReview } from "./DmrlReview";

function makeRow(overrides: Partial<DmrlRow>): DmrlRow {
  return {
    index: 0,
    arbo: "1",
    dmc: "",
    title: "Section",
    dm_type: "",
    icn: "",
    is_pm_title: false,
    matched: false,
    match_rank: "",
    page: null,
    matched_text: "",
    ...overrides,
  };
}

describe("DMRL review", () => {
  it("alerts only for missing DMs and labels publication-only titles", () => {
    const markup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [
          makeRow({ is_pm_title: true, title: "Introduction" }),
          makeRow({
            index: 1,
            dmc: "DMC-PUMP-A-00-00-00-00A-040A-D",
            is_pm_title: false,
            title: "Missing chapter",
          }),
          makeRow({
            index: 2,
            dmc: "DMC-PUMP-A-00-00-00-00A-041A-D",
            is_pm_title: false,
            matched: true,
            match_rank: "exact",
            title: "Found chapter",
          }),
        ],
        dmCount: 2,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );

    expect(markup).toContain('role="status"');
    expect(markup).toContain("migration.dmrl.missingAlert:1");
    expect(markup).toContain("migration.dmrl.pmTitle");
    expect(markup).toContain("migration.dmrl.exclude");
    expect(markup.match(/migration\.dmrl\.exclude/g)).toHaveLength(1);
    expect(markup.indexOf("migration.dmrl.exclude")).toBeLessThan(
      markup.indexOf("migration.dmrl.titleInput"),
    );
    expect(markup).toContain("Found chapter");
  });

  it("does not alert when the only unmatched row is a publication title", () => {
    const markup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [makeRow({ is_pm_title: true })],
        dmCount: 0,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );

    expect(markup).not.toContain('role="status"');
    expect(markup).not.toContain("migration.dmrl.exclude");
  });
});
