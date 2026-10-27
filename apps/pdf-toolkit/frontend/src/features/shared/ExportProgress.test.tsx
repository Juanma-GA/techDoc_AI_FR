import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ExportProgress } from "./ExportProgress";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: { completed?: number; total?: number }) =>
      key === "exportProgress.pages"
        ? `Pages ${values?.completed ?? 0} / ${values?.total ?? 0}`
        : key,
  }),
}));

describe("ExportProgress", () => {
  it("exposes measured page progress as a percentage", () => {
    const markup = renderToStaticMarkup(
      <ExportProgress progress={{ phase: "pages", percentage: 50, completed: 2, total: 4 }} />,
    );

    expect(markup).toContain('aria-label="Pages 2 / 4"');
    expect(markup).toContain('aria-valuenow="50"');
    expect(markup).toContain(">50%</span>");
  });

  it("does not claim a percentage while server processing is unmeasured", () => {
    const markup = renderToStaticMarkup(
      <ExportProgress progress={{ phase: "processing", percentage: null }} />,
    );

    expect(markup).toContain('aria-label="exportProgress.processing"');
    expect(markup).not.toContain("aria-valuenow=");
    expect(markup).not.toContain("%</span>");
  });
});
