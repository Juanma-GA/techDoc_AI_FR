// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
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
import { DmrlTypeConflictNotice } from "./DmrlTypeConflictNotice";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

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
  it("uses the shared type menu and padded conflict notices", () => {
    const notice = renderToStaticMarkup(
      createElement(DmrlTypeConflictNotice, {
        rows: [makeRow({
          dm_type: "descriptive",
          type_conflict: true,
          type_issue: "unsupported_schema",
        })],
      }),
    );
    expect(notice).toContain("p-4 sm:p-5");
    expect(notice).toContain("space-y-2 pl-5 leading-6");

    const review = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [makeRow({
          index: 1,
          type_conflict: true,
          type_issue: "unsupported_schema",
        })],
        dmCount: 1,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );
    expect(review).toContain("s1k-dm-type-select");
  });

  it("allows the resolved warning details to be folded and unfolded", async () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    try {
      await act(async () => {
        root.render(createElement(DmrlTypeConflictNotice, {
          rows: [makeRow({
            dm_type: "descriptive",
            dmrl_type: "DESCR",
            info_code: "001",
            info_code_schema: "frontmatter",
            type_conflict: true,
            type_issue: "unsupported_schema",
          })],
        }));
      });

      const details = host.querySelector("details");
      const summary = details?.querySelector("summary");
      expect(details?.open).toBe(false);
      expect(summary).not.toBeNull();

      await act(async () => summary?.click());
      expect(details?.open).toBe(true);

      await act(async () => summary?.click());
      expect(details?.open).toBe(false);
    } finally {
      await act(async () => root.unmount());
      host.remove();
    }
  });

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

  it("keeps source pages on exact matches but removes page and approximation wording from checks", () => {
    const markup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [
          makeRow({ matched: true, match_rank: "exact", page: 1 }),
          makeRow({ index: 1, matched: true, match_rank: "prefix", page: 2 }),
          makeRow({ index: 2, matched: true, match_rank: "contains", page: 3 }),
        ],
        dmCount: 3,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );

    expect(markup).toContain("migration.match.exact:1");
    expect(markup).toContain("migration.match.prefix");
    expect(markup).toContain("migration.match.contains");
    expect(markup).not.toContain("migration.match.prefix:");
    expect(markup).not.toContain("migration.match.contains:");
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

  it("uses a recognized DMRL fallback while preserving the InfoCode warning", () => {
    const markup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [
          makeRow({
            index: 1,
            dmc: "DMC-PUMP-A-00-00-00-00A-001A-D",
            title: "Terminologie",
            dm_type: "descriptive",
            dmrl_type: "DESCR",
            info_code: "001",
            info_code_schema: "frontmatter",
            info_code_dm_type: "",
            type_conflict: true,
            type_issue: "unsupported_schema",
            matched: true,
            match_rank: "exact",
          }),
        ],
        dmCount: 1,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );

    expect(markup).toContain('role="status"');
    expect(markup).toContain("migration.dmrl.typeConflict");
    expect(markup).toContain("migration.dmrl.unsupportedSchema");
    expect(markup).toContain("migration.dmrl.typeSelected:dmType.descriptive");
    expect(markup).toContain("dmType.descriptive");
    expect(markup).not.toContain("migration.dmrl.typeResolutionRequiredRow");
    expect(markup).not.toContain("migration.dmrl.selectType");
    expect(markup).not.toContain('open=""');
    const validateButton = markup.match(
      /<button\b[^>]*>migration\.dmrl\.validate<\/button>/,
    )?.[0] ?? "";
    expect(validateButton).not.toMatch(/\sdisabled(?:\s|>)/);
    expect(markup).toContain('href="#dmrl-type-1"');
    expect(markup).toContain('id="dmrl-type-1"');
  });

  it("opens unresolved warnings and still requires a type when DMRL has no recognized fallback", () => {
    const row = makeRow({
      index: 1,
      dmc: "DMC-PUMP-A-00-00-00-00A-520A-D",
      title: "Removal Procedure",
      dmrl_type: "Unknown category",
      info_code: "001",
      info_code_schema: "frontmatter",
      type_conflict: true,
      type_issue: "unsupported_schema",
      matched: true,
      match_rank: "exact",
    });
    const pendingMarkup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [row],
        dmCount: 1,
        busy: true,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );
    const pendingSelect = pendingMarkup.match(
      /<button\b[^>]*aria-label="migration\.dmrl\.typeLabel:Removal Procedure"[^>]*>/,
    )?.[0] ?? "";
    expect(pendingSelect).toContain("s1k-dm-type-select");
    expect(pendingSelect).toContain('disabled=""');
    expect(pendingMarkup).toContain('role="alert"');
    expect(pendingMarkup).toContain('open=""');
    expect(pendingMarkup).toContain("migration.dmrl.selectType");
    expect(pendingMarkup).toContain("migration.dmrl.typeResolutionRequiredRow");

    const resolvedMarkup = renderToStaticMarkup(
      createElement(DmrlReview, {
        rows: [{ ...row, dm_type: "procedural" }],
        dmCount: 1,
        busy: false,
        edits: {},
        onTitleChange: vi.fn(),
        onUpdate: vi.fn(),
        onAdvance: vi.fn(),
      }),
    );
    const resolvedButton = resolvedMarkup.match(
      /<button\b[^>]*>migration\.dmrl\.validate<\/button>/,
    )?.[0] ?? "";
    expect(resolvedButton).not.toMatch(/\sdisabled(?:\s|>)/);
  });
});
