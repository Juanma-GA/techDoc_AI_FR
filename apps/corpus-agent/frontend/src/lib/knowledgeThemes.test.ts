import { describe, expect, it } from "vitest";

import { knowledgeCapitalization, knowledgeThemes, type KnowledgeEntry } from "./knowledgeThemes";
import type { AnomalyOut } from "./types";

function entry(overrides: Partial<AnomalyOut> = {}, sourceId: string | null = "file-a"): KnowledgeEntry {
  return {
    project: "Synthetic project",
    filename: "synthetic.xlsx",
    sourceId,
    anomaly: {
      id: "ticket", project_id: "project-a", file_version_id: "version-a", run_id: "run-a",
      type: "personnalisee", category: "Sécurité", severity: "high", confidence: "elevee",
      message: "Missing warning", suggestion: "Add a warning.", evidence: "", location: "",
      message_key: null, message_params_json: null, suggestion_key: null, suggestion_params_json: null,
      status: "fixed", created_at: "2026-10-01T10:00:00Z", resolved_at: "2026-10-02T10:00:00Z",
      ...overrides,
    },
  };
}

describe("knowledgeThemes", () => {
  it("groups subjects and duplicate lessons while retaining every source correction", () => {
    const themes = knowledgeThemes([
      entry(),
      entry({ id: "second", category: " securite ", suggestion: " ADD  A WARNING. ", resolved_at: "2026-10-03T10:00:00Z" }),
      entry({ id: "third", project_id: "project-b", suggestion: "Check isolation." }, "file-b"),
    ], "en");
    expect(themes).toHaveLength(1);
    expect(themes[0]).toMatchObject({
      sourceCount: 2, projectCount: 2, latest: "2026-10-03T10:00:00Z",
      lessons: [{ text: "Add a warning.", count: 2 }, { text: "Check isolation.", count: 1 }],
    });

    expect(themes[0]?.corrections).toHaveLength(3);
  });

  it("never converts open or rejected tickets into lessons", () => {
    const themes = knowledgeThemes([
      entry(),
      entry({ status: "open", suggestion: "Unvalidated proposal" }),
      entry({ status: "acknowledged" }),
      entry({ status: "rejected" }),
      entry({ status: "open", category: "Other theme" }),
    ], "en");
    expect(themes).toHaveLength(1);
    expect(themes[0]?.pendingCount).toBe(2);
    expect(themes[0]?.lessons).toEqual([{ text: "Add a warning.", count: 1 }]);
  });

  it("does not invent a recommendation, source document or date when absent", () => {
    const themes = knowledgeThemes([entry({ category: " ", suggestion: "", resolved_at: null }, null)], "en");
    expect(themes[0]).toMatchObject({ title: "", lessons: [], sourceCount: 0 });
    expect(themes[0]?.latest).toBeUndefined();
    expect(knowledgeThemes([], "en")).toEqual([]);
  });
});

describe("knowledgeCapitalization", () => {
  it("measures distinct lessons and documents without counting open or rejected proposals", () => {
    expect(knowledgeCapitalization([
      entry(),
      entry({ id: "second", suggestion: " ADD A WARNING. " }),
      entry({ id: "third", category: "Tools", suggestion: "" }, "file-b"),
      entry({ status: "open" }, "file-c"),
      entry({ status: "rejected" }, "file-d"),
    ], "en")).toMatchObject({
      correctionCount: 3, lessonCount: 1, sourceCount: 2, themeCount: 2, toFormalize: 1,
      timeline: [{ day: "2026-10-02", added: 3, cumulative: 3 }],
    });
  });

  it("orders UTC resolution days and excludes missing and invalid dates from the timeline", () => {
    const result = knowledgeCapitalization([
      entry({ resolved_at: "2026-10-04T00:30:00+02:00" }),
      entry({ resolved_at: "2026-10-02T10:00:00Z" }),
      entry({ resolved_at: null }),
      entry({ resolved_at: "invalid" }),
    ], "en");
    expect(result.timeline).toEqual([
      { day: "2026-10-02", added: 1, cumulative: 1 },
      { day: "2026-10-03", added: 1, cumulative: 2 },
    ]);
    expect(result.undatedCount).toBe(2);
    expect(knowledgeCapitalization([], "en")).toMatchObject({ correctionCount: 0, lessonCount: 0, timeline: [] });
  });
});
